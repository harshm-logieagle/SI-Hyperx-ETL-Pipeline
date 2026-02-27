document.addEventListener('DOMContentLoaded', () => {
    const queueBody = document.getElementById('queue-body');
    const queueCount = document.getElementById('queue-count');
    const discoverBtn = document.getElementById('discover-btn');
    const startWorkerBtn = document.getElementById('start-worker-btn');
    const modal = document.getElementById('preview-modal');
    const closeBtn = document.querySelector('.close');
    const brandSearch = document.getElementById('brand-search');
    const searchResults = document.getElementById('search-results');
    const configForm = document.getElementById('brand-config-form');

    const managedBody = document.getElementById('managed-body');
    const manageFilter = document.getElementById('brand-manage-filter');

    let currentItem = null;
    let selectedBrand = null;
    let allManagedBrands = [];
    let editingType = 'queue'; // 'queue' or 'cluster'

    async function fetchQueue() {
        try {
            const resp = await fetch('/api/queue');
            const data = await resp.json();
            renderQueue(data);
        } catch (e) {
            console.error('Fetch error:', e);
        }
    }

    async function fetchManaged() {
        try {
            const resp = await fetch('/api/brands/all');
            const data = await resp.json();
            allManagedBrands = data;
            renderManaged(data);
        } catch (e) {
            console.error('Fetch Managed error:', e);
        }
    }

    function renderQueue(items) {
        queueCount.innerText = `${items.length} Brands`;
        queueBody.innerHTML = items.map(item => `
            <tr>
                <td><strong>${item.brand_name}</strong></td>
                <td>
                    ${item.master_outlet_id}
                    <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 4px;">
                        Config: ${item.sample_size} calls, >${item.min_duration}s
                    </div>
                </td>
                <td><span class="status-badge status-${item.status}">${item.status}</span></td>
                <td><span class="badge">${item.stage || 'N/A'}</span></td>
                <td style="font-size: 0.8rem; color: #94a3b8">${item.created_at}</td>
                <td>
                    ${(item.status === 'review_pending' || item.status === 'completed') ?
                `<button class="btn btn-secondary btn-sm" onclick="openPreview(${item.id})">Preview</button>` :
                (item.status === 'failed' ? `<span title="${item.error_message || ''}" style="cursor:help">❌ Fail</span>` :
                    '<button class="btn btn-secondary btn-sm" disabled>Wait</button>')}
                </td>
            </tr>
        `).join('');
    }

    function renderManaged(items) {
        managedBody.innerHTML = items.map(item => `
            <tr>
                <td><strong>${item.brand_name}</strong></td>
                <td>${item.id}</td>
                <td>
                    <span class="status-badge ${item.cluster_id ? 'status-active' : 'status-missing'}">
                        ${item.cluster_id ? 'Clustered' : 'Pending'}
                    </span>
                </td>
                <td style="font-size: 0.8rem; color: #94a3b8">${item.clustered_at || 'Never'}</td>
                <td>
                    <div class="action-group">
                        ${item.cluster_id ?
                `<button class="btn btn-secondary btn-sm" onclick="editExistingCluster(${item.id})"><i class="fas fa-edit"></i> Edit</button>` : ''
            }
                        <button class="btn btn-primary btn-sm" onclick="regenerateCluster(${item.id}, '${item.brand_name}')">
                            <i class="fas fa-redo"></i> ${item.cluster_id ? 'Re-generate' : 'Generate'}
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    manageFilter.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = allManagedBrands.filter(b =>
            b.brand_name.toLowerCase().includes(query) ||
            b.id.toString().includes(query)
        );
        renderManaged(filtered);
    });

    // Brand Search Logic
    brandSearch.addEventListener('input', async (e) => {
        const query = e.target.value;
        if (query.length < 2) {
            searchResults.style.display = 'none';
            return;
        }

        const resp = await fetch(`/api/brands/search?q=${query}`);
        const brands = await resp.json();

        if (brands.length > 0) {
            searchResults.innerHTML = brands.map(b => `
                <div class="search-result-item" onclick="selectBrand(${b.id}, '${b.brand_name}')">
                    ${b.brand_name} (${b.id})
                </div>
            `).join('');
            searchResults.style.display = 'block';
        } else {
            searchResults.style.display = 'none';
        }
    });

    window.selectBrand = async (id, name) => {
        selectedBrand = { id, name };
        searchResults.style.display = 'none';
        brandSearch.value = name;

        document.getElementById('selected-brand-name').innerText = name;
        configForm.style.display = 'block';

        // Scroll to config form
        configForm.scrollIntoView({ behavior: 'smooth' });

        const statusBadge = document.getElementById('cluster-status-badge');
        statusBadge.innerText = 'Checking...';

        const resp = await fetch(`/api/brands/${id}/cluster`);
        const { exists } = await resp.json();

        if (exists) {
            statusBadge.innerText = 'Existing Cluster Found (Will Re-generate)';
            statusBadge.style.color = '#eab308';
        } else {
            statusBadge.innerText = 'No Existing Cluster';
            statusBadge.style.color = '#22c55e';
        }
    };

    window.regenerateCluster = (id, name) => {
        window.selectBrand(id, name);
    };

    window.editExistingCluster = async (id) => {
        editingType = 'cluster';
        const resp = await fetch(`/api/clusters/${id}`);
        const item = await resp.json();
        currentItem = item; // Using generic currentItem for the modal

        document.getElementById('modal-brand-name').innerText = `${item.brand_name} - Edit Existing Cluster`;
        document.getElementById('product-hierarchy-editor').value = JSON.stringify(item.result_json.product_heirarchy_list, null, 2);
        document.getElementById('complaint-reasons-editor').value = JSON.stringify(item.result_json.complaint_reasons, null, 2);
        document.getElementById('enquiry-reasons-editor').value = JSON.stringify(item.result_json.enquiry_reasons, null, 2);
        document.getElementById('request-reasons-editor').value = JSON.stringify(item.result_json.request_reasons, null, 2);

        // Hide approve button for direct edits from management
        document.getElementById('approve-btn').style.display = 'none';
        modal.style.display = 'block';
    };

    document.getElementById('cancel-config-btn').onclick = () => {
        configForm.style.display = 'none';
        brandSearch.value = '';
        selectedBrand = null;
    };

    document.getElementById('add-to-queue-btn').onclick = async () => {
        if (!selectedBrand) return;

        const config = {
            master_outlet_id: selectedBrand.id,
            brand_name: selectedBrand.name,
            sample_size: parseInt(document.getElementById('config-sample-size').value),
            min_duration: parseInt(document.getElementById('config-min-duration').value),
            start_date: document.getElementById('config-start-date').value || null,
            end_date: document.getElementById('config-end-date').value || null
        };

        const resp = await fetch('/api/queue/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        if (resp.ok) {
            alert('Added to queue!');
            configForm.style.display = 'none';
            brandSearch.value = '';
            fetchQueue();
        } else {
            alert('Failed to add to queue');
        }
    };

    window.openPreview = async (id) => {
        editingType = 'queue';
        const resp = await fetch(`/api/queue/${id}`);
        const item = await resp.json();
        currentItem = item;

        document.getElementById('modal-brand-name').innerText = `${item.brand_name} - Clustered Results`;
        document.getElementById('product-hierarchy-editor').value = JSON.stringify(item.result_json.product_heirarchy_list, null, 2);
        document.getElementById('complaint-reasons-editor').value = JSON.stringify(item.result_json.complaint_reasons, null, 2);
        document.getElementById('enquiry-reasons-editor').value = JSON.stringify(item.result_json.enquiry_reasons, null, 2);
        document.getElementById('request-reasons-editor').value = JSON.stringify(item.result_json.request_reasons, null, 2);

        document.getElementById('approve-btn').style.display = 'inline-flex';
        modal.style.display = 'block';
    }

    closeBtn.onclick = () => modal.style.display = 'none';

    document.getElementById('save-btn').onclick = async () => {
        const updated = {
            result_json: {
                product_heirarchy_list: JSON.parse(document.getElementById('product-hierarchy-editor').value),
                complaint_reasons: JSON.parse(document.getElementById('complaint-reasons-editor').value),
                enquiry_reasons: JSON.parse(document.getElementById('enquiry-reasons-editor').value),
                request_reasons: JSON.parse(document.getElementById('request-reasons-editor').value)
            }
        };

        const url = editingType === 'queue' ?
            `/api/queue/${currentItem.id}/update` :
            `/api/clusters/${currentItem.master_outlet_id}/update`;

        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });

        if (resp.ok) {
            // Also update cluster table if we're saving a completed queue item
            if (editingType === 'queue' && currentItem.status === 'completed') {
                await fetch(`/api/clusters/${currentItem.master_outlet_id}/update`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updated)
                });
            }
            alert('Changes saved!');
            if (editingType === 'cluster') modal.style.display = 'none';
            fetchQueue();
            fetchManaged();
        } else {
            alert('Error saving changes');
        }
    };

    document.getElementById('approve-btn').onclick = async () => {
        if (!confirm('Are you sure you want to approve and store these results?')) return;

        const updated = {
            result_json: {
                product_heirarchy_list: JSON.parse(document.getElementById('product-hierarchy-editor').value),
                complaint_reasons: JSON.parse(document.getElementById('complaint-reasons-editor').value),
                enquiry_reasons: JSON.parse(document.getElementById('enquiry-reasons-editor').value),
                request_reasons: JSON.parse(document.getElementById('request-reasons-editor').value)
            }
        };

        const resp = await fetch(`/api/queue/${currentItem.id}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });

        if (resp.ok) {
            const res = await resp.json();
            alert(res.message);
            modal.style.display = 'none';
            fetchQueue();
            fetchManaged();
        } else {
            alert('Failed to approve and save');
        }
    };

    discoverBtn.onclick = async () => {
        await fetch('/api/discover', { method: 'POST' });
        alert('Discovery process triggered');
        fetchQueue();
    };

    startWorkerBtn.onclick = async () => {
        await fetch('/api/worker/start', { method: 'POST' });
        alert('Worker started in background');
    };

    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if (!brandSearch.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });

    // Initial fetch
    fetchQueue();
    fetchManaged();

    // Poll queue every 5 seconds
    setInterval(fetchQueue, 5000);

    // ===== Tab Switching =====
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });

    // ===== Select2 Initialisation =====
    const s2Opts = (placeholder, ajaxUrl = null) => {
        const opts = {
            placeholder,
            allowClear: true,
            dropdownParent: $('#tab-excel-push'),
            width: '100%',
        };
        if (ajaxUrl) {
            opts.minimumInputLength = 1;
            opts.ajax = {
                url: ajaxUrl,
                dataType: 'json',
                delay: 300,
                data: params => ({ q: params.term }),
                processResults: data => ({
                    results: data.map(d => ({ id: d.id ?? d, text: d.name ?? d }))
                }),
            };
        }
        return opts;
    };

    // Master outlet ID — free-text (tags mode) so user can type any numeric ID
    $('#excel-master-outlet-id').select2({
        placeholder: 'Type master outlet ID…',
        allowClear: true,
        tags: true,
        dropdownParent: $('#tab-excel-push'),
        width: '100%',
        createTag: params => ({ id: params.term.trim(), text: params.term.trim(), newTag: true }),
    });
    $('#excel-state').select2(s2Opts('Select state…'));
    // City — free-text (tags mode) so user can type any city name
    $('#excel-city').select2({
        placeholder: 'Type city name…',
        allowClear: true,
        tags: true,
        dropdownParent: $('#tab-excel-push'),
        width: '100%',
        createTag: params => ({ id: params.term.trim(), text: params.term.trim(), newTag: true }),
    });

    // ===== Outlet ID Tag Input =====
    const tagWrapper   = document.getElementById('outlet-tag-wrapper');
    const tagsArea     = document.getElementById('outlet-tags');
    const tagTextInput = document.getElementById('outlet-tag-input');
    const hiddenOutlet = document.getElementById('excel-outlet-id');
    let outletTags     = [];

    function renderOutletTags() {
        tagsArea.innerHTML = '';
        outletTags.forEach((tag, i) => {
            const chip = document.createElement('span');
            chip.className = 'outlet-chip';
            chip.innerHTML = `${tag}<button type="button" class="chip-remove" title="Remove">&times;</button>`;
            chip.querySelector('.chip-remove').addEventListener('click', () => {
                outletTags.splice(i, 1);
                renderOutletTags();
            });
            tagsArea.appendChild(chip);
        });
        hiddenOutlet.value = outletTags.join(',');
    }

    function addOutletTag(raw) {
        raw.split(',').map(v => v.trim()).filter(Boolean).forEach(v => {
            if (!outletTags.includes(v)) outletTags.push(v);
        });
        renderOutletTags();
    }

    tagTextInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            const val = tagTextInput.value.replace(/,$/, '').trim();
            if (val) addOutletTag(val);
            tagTextInput.value = '';
        } else if (e.key === 'Backspace' && tagTextInput.value === '' && outletTags.length) {
            outletTags.pop();
            renderOutletTags();
        }
    });

    tagTextInput.addEventListener('paste', e => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        addOutletTag(pasted);
        tagTextInput.value = '';
    });

    // Clicking anywhere in the wrapper focuses the text input
    tagWrapper.addEventListener('click', () => tagTextInput.focus());

    // ===== Excel Push: Reset Button =====
    document.getElementById('excel-reset-btn').addEventListener('click', () => {
        $('#excel-master-outlet-id').val(null).trigger('change');
        $('#excel-state').val(null).trigger('change');
        $('#excel-city').val(null).trigger('change');
        outletTags = [];
        renderOutletTags();
        tagTextInput.value = '';
        ['excel-from-date', 'excel-to-date', 'excel-num-records'].forEach(id => {
            document.getElementById(id).value = '';
        });
    });

    // ===== Excel Push: Run Query Button =====
    document.getElementById('excel-run-btn').addEventListener('click', async () => {
        const masterId = $('#excel-master-outlet-id').val();
        if (!masterId) {
            alert('Please enter a Master Outlet ID before running the query.');
            return;
        }

        const config = {
            master_outlet_id: masterId,
            outlet_ids:  document.getElementById('excel-outlet-id').value || null,
            state:       $('#excel-state').val() || null,
            city:        $('#excel-city').val() || null,
            from_date:   document.getElementById('excel-from-date').value || null,
            to_date:     document.getElementById('excel-to-date').value || null,
            num_records: parseInt(document.getElementById('excel-num-records').value) || 200000,
        };

        const runBtn = document.getElementById('excel-run-btn');
        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';

        try {
            const resp = await fetch('/api/excel-push/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            const result = await resp.json();
            if (resp.ok) {
                fetchExcelPushJobs();   // immediate refresh
            } else {
                alert('Failed to start push job: ' + (result.detail || 'Unknown error'));
            }
        } catch (e) {
            alert('Network error: ' + e.message);
        } finally {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="fas fa-play"></i> Run Query';
        }
    });

    // ===== Excel Push: Jobs Table =====
    let excelJobsHasActive = false;   // drives polling frequency
    let excelJobsPollTimer = null;

    function excelJobStatusClass(status) {
        return {
            pending:   'status-pending',
            running:   'status-processing',
            completed: 'status-completed',
            failed:    'status-failed',
        }[status] || 'status-pending';
    }

    function renderExcelPushJobs(jobs) {
        const tbody = document.getElementById('excel-jobs-body');
        const countBadge = document.getElementById('excel-jobs-count');

        if (!jobs || jobs.length === 0) {
            tbody.innerHTML = `<tr id="excel-jobs-empty-row">
                <td colspan="6" style="text-align:center; color:var(--text-muted); padding:2rem;">
                    No push jobs yet. Configure and click <strong>Run Query</strong> to start one.
                </td></tr>`;
            countBadge.textContent = '0 Jobs';
            return;
        }

        countBadge.textContent = `${jobs.length} Job${jobs.length !== 1 ? 's' : ''}`;
        excelJobsHasActive = jobs.some(j => j.status === 'running' || j.status === 'pending');

        tbody.innerHTML = jobs.map(job => {
            const total  = job.total_records  || 0;
            const pushed = job.pushed_records || 0;
            const pct    = total > 0 ? Math.round((pushed / total) * 100) : (job.status === 'completed' ? 100 : 0);

            const progressBar = `
                <div class="push-progress-wrap">
                    <div class="push-progress-track">
                        <div class="push-progress-fill ${job.status === 'failed' ? 'push-progress-fail' : ''}"
                             style="width:${pct}%"></div>
                    </div>
                    <span class="push-progress-label">${
                        job.status === 'completed'
                            ? `${pushed.toLocaleString()} pushed`
                            : total > 0
                                ? `${pushed.toLocaleString()} / ${total.toLocaleString()}`
                                : '—'
                    }</span>
                </div>`;

            const outletDisplay = job.outlet_ids
                ? job.outlet_ids.split(',').slice(0, 3).join(', ') + (job.outlet_ids.split(',').length > 3 ? '…' : '')
                : '—';

            return `<tr>
                <td style="font-size:0.8rem;color:var(--text-muted)">#${job.id}</td>
                <td>
                    <strong>${job.master_outlet_id}</strong>
                    ${outletDisplay !== '—' ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-top:3px">Outlets: ${outletDisplay}</div>` : ''}
                </td>
                <td><span class="status-badge ${excelJobStatusClass(job.status)}">${job.status}</span></td>
                <td style="font-size:0.82rem;color:var(--text-muted);max-width:260px">${job.stage || '—'}</td>
                <td style="min-width:180px">${progressBar}</td>
                <td style="font-size:0.78rem;color:var(--text-muted)">${job.created_at.split('.')[0]}</td>
            </tr>`;
        }).join('');
    }

    async function fetchExcelPushJobs() {
        try {
            const resp = await fetch('/api/excel-push/jobs');
            const jobs = await resp.json();
            renderExcelPushJobs(jobs);
        } catch (e) {
            console.error('fetchExcelPushJobs error:', e);
        }
    }

    function scheduleExcelJobsPoll() {
        clearTimeout(excelJobsPollTimer);
        // Poll every 2 s when a job is active, 10 s otherwise
        const delay = excelJobsHasActive ? 2000 : 10000;
        excelJobsPollTimer = setTimeout(async () => {
            await fetchExcelPushJobs();
            scheduleExcelJobsPoll();
        }, delay);
    }

    // Initial load + start adaptive polling
    fetchExcelPushJobs();
    scheduleExcelJobsPoll();
});
