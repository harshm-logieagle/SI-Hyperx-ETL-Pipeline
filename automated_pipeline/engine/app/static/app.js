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
});
