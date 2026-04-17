"""
ETL Orchestrator — runs the 11 live-migration scripts on a 30-minute schedule,
respecting their dependency DAG.

Behavior:
    - Every 30 minutes, a pipeline run is triggered.
    - Tasks with all dependencies satisfied run in parallel (subprocess).
    - Downstream tasks wait for upstream success before starting.
    - If an upstream task fails (non-zero exit), all transitive downstream
      tasks are SKIPPED (not run). Sibling branches continue.
    - max_instances=1 + coalesce=True: if a run is still going when the next
      tick fires, the tick is skipped (no overlap). Missed ticks are coalesced.
    - In-memory scheduler (APScheduler BlockingScheduler). No persistence —
      if the orchestrator is restarted mid-run, the current pipeline run is
      interrupted, but each script's own checkpoint ensures safe resume on
      the next scheduled tick.

Each script already emails on permanent batch failure and on unhandled crash
via _etl_utils. This orchestrator does NOT duplicate those emails — it only
logs orchestration-level events.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from _etl_utils import install_crash_notifier

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("etl_orchestrator.log", encoding="utf-8"),
    ],
)
# Quiet APScheduler's own chatter except WARNING+
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger("ETL_ORCHESTRATOR")

SCRIPTS_DIR     = Path(__file__).resolve().parent
INTERVAL_MIN    = 30
MAX_PARALLEL    = 4      # cap on concurrent subprocesses within one pipeline run

# ─────────────────────────────────────────────────────────
# DAG definition
# Dependency edges reflect which target tables each script reads from.
# A node starts only after every node in `deps` has exited 0.
# ─────────────────────────────────────────────────────────
TASKS: Dict[str, Dict] = {
    # Root: reads outlets_raw only
    "brands":                     {"script": "brands.py",                     "deps": []},

    # Needs brands
    "outlets":                    {"script": "outlets.py",                    "deps": ["brands"]},
    "master_outlet_categories":   {"script": "master_outlet_categories.py",   "deps": ["brands"]},

    # Needs master_outlet_categories
    "master_outlet_products":     {"script": "master_outlet_products.py",     "deps": ["master_outlet_categories"]},

    # Needs outlets
    "customer_call_recordings":   {"script": "customer_call_recordings.py",   "deps": ["outlets"]},
    "master_outlet_call_reasons": {"script": "master_outlet_call_reasons.py", "deps": ["outlets"]},

    # Needs customer_call_recordings
    "call_recording_analytics":   {"script": "call_recording_analytics.py",   "deps": ["customer_call_recordings"]},

    # Fan-out from call_recording_analytics
    "call_analytics_emotions":    {"script": "call_analytics_emotions.py",    "deps": ["call_recording_analytics"]},
    "call_reasons":               {"script": "call_reasons.py",               "deps": ["call_recording_analytics",
                                                                                        "master_outlet_call_reasons"]},
    "call_product_mentions":      {"script": "call_product_mentions.py",      "deps": ["call_recording_analytics",
                                                                                        "master_outlet_products"]},

    # Needs call_product_mentions
    "call_product_mention_tags":  {"script": "call_product_mention_tags.py",  "deps": ["call_product_mentions"]},
}


def _validate_dag() -> None:
    """Fail fast at startup if DAG references unknown tasks or has a cycle."""
    names = set(TASKS)
    for name, meta in TASKS.items():
        for dep in meta["deps"]:
            if dep not in names:
                raise ValueError(f"Task '{name}' depends on unknown task '{dep}'")
        if not (SCRIPTS_DIR / meta["script"]).exists():
            raise FileNotFoundError(f"Script for '{name}' not found: {meta['script']}")

    # Cycle detection via Kahn's algorithm
    indeg = {n: len(m["deps"]) for n, m in TASKS.items()}
    queue = [n for n, d in indeg.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop()
        visited += 1
        for other, meta in TASKS.items():
            if n in meta["deps"]:
                indeg[other] -= 1
                if indeg[other] == 0:
                    queue.append(other)
    if visited != len(TASKS):
        raise ValueError("Cycle detected in task DAG")


def _run_script(name: str) -> int:
    """
    Run a single script as a subprocess. Returns the exit code.
    stdout/stderr are piped into the orchestrator log (prefixed) so everything
    is captured in etl_orchestrator.log. The script also writes its own
    etl_<name>.log file via its own logging config.
    """
    script_path = SCRIPTS_DIR / TASKS[name]["script"]
    logger.info(f"[{name}] starting: {script_path}")
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(SCRIPTS_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception as e:
        logger.error(f"[{name}] failed to spawn subprocess: {e}")
        return -1

    duration = time.monotonic() - start
    # Tail the last few lines into the orchestrator log for quick visibility.
    tail = (proc.stdout or "").strip().splitlines()[-10:]
    for line in tail:
        logger.info(f"[{name}] {line}")

    if proc.returncode == 0:
        logger.info(f"[{name}] ✓ completed in {duration:.1f}s")
    else:
        logger.error(f"[{name}] ✗ exit={proc.returncode} after {duration:.1f}s "
                     f"(see etl_{name}.log for details)")
    return proc.returncode


def _transitive_downstream(root: str) -> Set[str]:
    """Return the set of tasks reachable from `root` via the deps graph (excluding root)."""
    result: Set[str] = set()
    frontier = [root]
    while frontier:
        n = frontier.pop()
        for other, meta in TASKS.items():
            if n in meta["deps"] and other not in result:
                result.add(other)
                frontier.append(other)
    return result


def run_pipeline() -> None:
    """
    One full DAG execution. Called on each APScheduler tick.
    """
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    logger.info("═" * 70)
    logger.info(f"PIPELINE RUN START  id={run_id}")
    logger.info("═" * 70)
    pipeline_start = time.monotonic()

    # Per-run state
    pending:   Set[str] = set(TASKS)
    completed: Set[str] = set()
    failed:    Set[str] = set()
    skipped:   Set[str] = set()
    in_flight: Dict[Future, str] = {}

    def ready_tasks() -> List[str]:
        return [
            n for n in pending
            if all(d in completed for d in TASKS[n]["deps"])
            and not any(d in failed or d in skipped for d in TASKS[n]["deps"])
        ]

    def cascade_skip(node: str) -> None:
        """Mark all transitive downstream of a failed node as SKIPPED."""
        for down in _transitive_downstream(node) & pending:
            pending.discard(down)
            skipped.add(down)
            logger.warning(f"[{down}] SKIPPED — upstream '{node}' failed")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        while pending or in_flight:
            # Launch every task whose deps are satisfied.
            for name in ready_tasks():
                pending.discard(name)
                fut = pool.submit(_run_script, name)
                in_flight[fut] = name

            if not in_flight:
                # Pending is non-empty but nothing is runnable — only reachable
                # if the DAG has an unsatisfiable dep (validation would have
                # caught it) or a branch is blocked without being cascaded.
                logger.error(
                    f"Pipeline stuck: {len(pending)} pending, none runnable "
                    f"({sorted(pending)}). Aborting run."
                )
                skipped.update(pending)
                pending.clear()
                break

            # Block until at least one subprocess finishes, then harvest all
            # that are done in this wakeup (there may be several).
            done, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)
            for fut in done:
                name = in_flight.pop(fut)
                rc = fut.result()
                if rc == 0:
                    completed.add(name)
                else:
                    failed.add(name)
                    cascade_skip(name)

    duration = time.monotonic() - pipeline_start
    logger.info("─" * 70)
    logger.info(f"PIPELINE RUN END    id={run_id}  duration={duration:.1f}s")
    logger.info(f"  completed : {len(completed)}  {sorted(completed)}")
    logger.info(f"  failed    : {len(failed)}     {sorted(failed)}")
    logger.info(f"  skipped   : {len(skipped)}    {sorted(skipped)}")
    logger.info("═" * 70)


def main() -> None:
    install_crash_notifier("etl_orchestrator")
    _validate_dag()

    scheduler = BlockingScheduler(timezone=os.environ.get("TZ", "Asia/Kolkata"))
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=INTERVAL_MIN),
        id="etl_pipeline",
        name="ETL DAG pipeline run",
        max_instances=1,      # skip overlapping runs if one is still going
        coalesce=True,        # collapse missed ticks into one
        misfire_grace_time=60,
        next_run_time=datetime.now(),  # fire immediately on startup, then every 30 min
    )

    logger.info("═" * 70)
    logger.info(f"ETL ORCHESTRATOR STARTED — interval {INTERVAL_MIN} minutes")
    logger.info(f"Scripts dir : {SCRIPTS_DIR}")
    logger.info(f"Tasks       : {len(TASKS)}")
    logger.info("═" * 70)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Orchestrator stopped by user (Ctrl+C / SIGTERM). "
                       "Any in-flight subprocess will continue to completion.")


if __name__ == "__main__":
    main()
