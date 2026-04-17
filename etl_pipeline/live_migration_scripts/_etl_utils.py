"""
Shared ETL reliability utilities.

Provides:
    - send_alert_email(subject, body)     : SMTP alert (env-driven config)
    - install_crash_notifier(script_name) : atexit + excepthook + SIGTERM hook
    - notify_on_permanent_failure(...)    : called when a batch exhausts retries

SMTP config is read from environment variables at send time (not import time),
so scripts can be imported in contexts where SMTP is unavailable without crashing.

Required env vars for email to send:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_TO
Optional:
    SMTP_FROM    (defaults to SMTP_USER)
    SMTP_USE_TLS (truthy: "1"/"true"/"yes"/"on"; defaults to enabled)
    ALERT_CC     (comma-separated CC recipients)

Loads `.env` from the project root on import via python-dotenv so scripts work
without an explicit export. If any required env var is still missing, email is
silently skipped and a warning is logged — local dev / CI runs don't fail.
"""
from __future__ import annotations

import atexit
import logging
import os
import signal
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from typing import Optional

try:
    from dotenv import load_dotenv, find_dotenv
    # find_dotenv() walks up parent dirs until it finds .env — lets scripts run
    # from any CWD and still pick up the project-root .env.
    load_dotenv(find_dotenv(usecwd=True), override=False)
except ImportError:
    pass

logger = logging.getLogger("ETL_UTILS")

_REQUIRED_ENV = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_TO")
_TRUTHY = {"1", "true", "yes", "on"}


def send_alert_email(subject: str, body: str) -> bool:
    """
    Send a plain-text alert email. Returns True on success, False otherwise.
    Never raises — alerting must not take down the ETL process itself.
    """
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        logger.warning(
            f"Email alert skipped (missing env: {', '.join(missing)}). "
            f"Subject: {subject}"
        )
        return False

    host      = os.environ["SMTP_HOST"]
    port      = int(os.environ["SMTP_PORT"])
    user      = os.environ["SMTP_USER"]
    password  = os.environ["SMTP_PASSWORD"]
    to_addr   = os.environ["ALERT_TO"]
    from_addr = os.environ.get("SMTP_FROM", user)
    use_tls   = os.environ.get("SMTP_USE_TLS", "1").strip().lower() in _TRUTHY
    cc_addr   = os.environ.get("ALERT_CC", "").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr
    msg.set_content(body)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                if use_tls:
                    s.starttls()
                    s.ehlo()
                s.login(user, password)
                s.send_message(msg)
        logger.info(f"Alert email sent to {to_addr} | subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        return False


def _host_tag() -> str:
    try:
        return f"{socket.gethostname()}"
    except Exception:
        return "unknown-host"


def notify_on_permanent_failure(
    script_name: str,
    batch_num: int,
    id_range: tuple,
    rows_skipped: int,
    error: BaseException,
) -> None:
    """Called when a batch has exhausted MAX_RETRIES or hit a non-retriable error."""
    subject = f"[ETL FAILURE] {script_name} | batch {batch_num} skipped"
    body = (
        f"Script   : {script_name}\n"
        f"Host     : {_host_tag()}\n"
        f"Batch    : {batch_num}\n"
        f"ID range : {id_range[0]} – {id_range[1]}\n"
        f"Rows lost: {rows_skipped}\n"
        f"Error    : {type(error).__name__}: {error}\n\n"
        f"The ETL continued past this batch. Checkpoint was advanced to avoid an\n"
        f"infinite loop on poisoned data. Investigate the source rows in the ID\n"
        f"range above before re-running.\n"
    )
    send_alert_email(subject, body)


def install_crash_notifier(script_name: str) -> None:
    """
    Install hooks so an email is sent if the process dies unexpectedly:
      - sys.excepthook  : catches unhandled exceptions
      - signal SIGTERM  : catches kill/systemd stop (best effort on Windows)
      - atexit          : final fallback; fires on any exit including sys.exit()

    Safe to call more than once; only the first call installs hooks.
    """
    if getattr(install_crash_notifier, "_installed", False):
        return
    install_crash_notifier._installed = True  # type: ignore[attr-defined]

    state = {"crashed": False, "notified": False, "reason": None}

    def _notify(reason: str, detail: str) -> None:
        if state["notified"]:
            return
        state["notified"] = True
        subject = f"[ETL CRASH] {script_name} | {reason}"
        body = (
            f"Script : {script_name}\n"
            f"Host   : {_host_tag()}\n"
            f"Reason : {reason}\n\n"
            f"{detail}\n"
        )
        send_alert_email(subject, body)

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # User-initiated; don't spam alerts.
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        state["crashed"] = True
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _notify(f"unhandled {exc_type.__name__}", tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _sigterm_handler(signum, frame):
        state["crashed"] = True
        _notify(
            f"terminated by signal {signum}",
            "Process received SIGTERM (likely kill or systemd stop).",
        )
        # Re-raise default behavior: exit non-zero.
        sys.exit(143)

    def _atexit():
        if state["crashed"] or state["notified"]:
            return
        # Clean exit — nothing to do.

    sys.excepthook = _excepthook
    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, OSError):
        # Not in main thread, or signal unsupported on this platform — skip.
        pass
    atexit.register(_atexit)
