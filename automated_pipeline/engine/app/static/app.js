document.addEventListener('DOMContentLoaded', () => {
    const queueBody = document.getElementById('queue-body');
    const queueCount = document.getElementById('queue-count');
    const discoverBtn = document.getElementById('discover-btn');
    const startWorkerBtn = document.getElementById('start-worker-btn');
    const modal = document.getElementById('preview-modal');
    const closeBtn = document.querySelector('.close');

    let currentItem = null;

    async function fetchQueue() {
        try {
            const resp = await fetch('/api/queue');
            const data = await resp.json();
            renderQueue(data);
        } catch (e) {
            console.error('Fetch error:', e);
        }
    }

    function renderQueue(items) {
        queueCount.innerText = `${items.length} Brands`;
        queueBody.innerHTML = items.map(item => `
            <tr>
                <td><strong>${item.brand_name}</strong></td>
                <td>${item.master_outlet_id}</td>
                <td><span class="status-badge status-${item.status}">${item.status}</span></td>
                <td><span class="badge">${item.stage || 'N/A'}</span></td>
                <td style="font-size: 0.8rem; color: #94a3b8">${item.created_at}</td>
                <td>
                    ${item.status === 'review_pending' ?
                `<button class="btn btn-secondary btn-sm" onclick="openPreview(${item.id})">Preview</button>` :
                '<button class="btn btn-secondary btn-sm" disabled>Wait</button>'}
                </td>
            </tr>
        `).join('');
    }

    window.openPreview = async (id) => {
        const resp = await fetch(`/api/queue/${id}`);
        const item = await resp.json();
        currentItem = item;

        document.getElementById('modal-brand-name').innerText = `${item.brand_name} - Clustered Results`;
        document.getElementById('product-hierarchy-editor').value = JSON.stringify(item.result_json.product_heirarchy_list, null, 2);
        document.getElementById('complaint-reasons-editor').value = JSON.stringify(item.result_json.complaint_reasons, null, 2);
        document.getElementById('enquiry-reasons-editor').value = JSON.stringify(item.result_json.enquiry_reasons, null, 2);
        document.getElementById('request-reasons-editor').value = JSON.stringify(item.result_json.request_reasons, null, 2);

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

        await fetch(`/api/queue/${currentItem.id}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });
        alert('Changes saved!');
        fetchQueue();
    };

    document.getElementById('approve-btn').onclick = async () => {
        if (!confirm('Are you sure you want to approve and store these results?')) return;

        await fetch(`/api/queue/${currentItem.id}/approve`, { method: 'POST' });
        modal.style.display = 'none';
        fetchQueue();
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

    // Poll every 5 seconds
    setInterval(fetchQueue, 5000);
    fetchQueue();
});
