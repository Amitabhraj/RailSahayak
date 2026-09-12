/* Rail-Sync AI Dynamic Client Engine */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Live Digital Clock Ticker
    function updateLiveClock() {
        const clockEl = document.getElementById('liveClockTicker');
        if (clockEl) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-IN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const dateStr = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
            clockEl.innerHTML = `<i class="fa-regular fa-clock me-1 text-info"></i> ${dateStr} | ${timeStr} IST`;
        }
    }
    updateLiveClock();
    setInterval(updateLiveClock, 1000);

    // 2. Mobile Sidebar Toggle
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    const sidebar = document.querySelector('.sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });
    }

    // 3. Trigger AI Optimizer AJAX
    const runOptForm = document.getElementById('runOptimizerForm');
    if (runOptForm) {
        runOptForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = runOptForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Optimizing Multi-Dept Blocks...`;

            const horizon = document.getElementById('optHorizonSelect')?.value || 'WEEKLY';
            const strategy = document.getElementById('optStrategySelect')?.value || 'MULTI_OBJECTIVE_BALANCED';

            try {
                const response = await fetch('/api/run-optimizer/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ horizon, strategy })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    showToast(`AI Optimization Successful! Generated ${data.blocks_generated} blocks with ${data.synergy_rate}% Synergy, saving ${data.total_downtime_saved_hours} hrs.`, 'success');
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    showToast(`Error: ${data.message || 'Optimization failed'}`, 'danger');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            } catch (err) {
                showToast(`Request failed: ${err.message}`, 'danger');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        });
    }

    // 4. Emergency Defect Injection AJAX
    const emgBtn = document.getElementById('btnInjectEmergency');
    if (emgBtn) {
        emgBtn.addEventListener('click', async () => {
            const defectType = document.getElementById('emgDefectTypeSelect')?.value || 'RAIL_FRACTURE';
            const corridorId = document.getElementById('emgCorridorSelect')?.value || '';

            emgBtn.disabled = true;
            emgBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Injecting...`;

            try {
                const res = await fetch('/api/inject-emergency/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ defect_type: defectType, corridor_id: corridorId })
                });
                const result = await res.json();
                if (result.status === 'success') {
                    showToast(`Emergency alert raised! Block ${result.block_id} scheduled immediately. AI Score: ${result.ai_score}`, 'danger');
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    showToast(result.message || 'Injection failed', 'danger');
                    emgBtn.disabled = false;
                    emgBtn.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> Inject & Re-Plan`;
                }
            } catch (err) {
                showToast(err.message, 'danger');
                emgBtn.disabled = false;
                emgBtn.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> Inject & Re-Plan`;
            }
        });
    }

    // 5. Live Co-Location Assistance in Department Portal
    const kmStartInput = document.getElementById('demandKmStart');
    const kmEndInput = document.getElementById('demandKmEnd');
    const corridorSelect = document.getElementById('demandCorridorSelect');
    const deptInput = document.getElementById('demandSourceSystem');

    async function checkCoLocation() {
        const corr = corridorSelect?.value;
        const kms = kmStartInput?.value;
        const kme = kmEndInput?.value;
        const dept = deptInput?.value || '';

        const container = document.getElementById('coLocationSuggestionsBox');
        if (!container) return;

        if (!corr || !kms || !kme) {
            container.innerHTML = `<div class="text-muted small"><i class="fa-solid fa-circle-info me-1"></i> Enter corridor and KM markers above to scan for potential multi-department shadow blocks.</div>`;
            return;
        }

        try {
            const resp = await fetch(`/api/check-co-location/?corridor_id=${corr}&km_start=${kms}&km_end=${kme}&dept=${dept}`);
            const data = await resp.json();

            if (data.candidates && data.candidates.length > 0) {
                let html = `
                    <div class="p-3 border border-success rounded bg-dark mb-2" style="border-left: 4px solid #10b981 !important;">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="badge badge-synergy"><i class="fa-solid fa-bolt me-1"></i> AI Shadow Opportunity Detected!</span>
                            <span class="small text-success">${data.candidates.length} co-located demand(s) nearby</span>
                        </div>
                        <div class="small text-light mb-2">Rail-Sync AI can combine your request with the following scheduled works to save duplicate block downtime:</div>
                        <ul class="list-unstyled mb-0">
                `;
                data.candidates.forEach(c => {
                    html += `
                        <li class="py-1 border-bottom border-secondary small d-flex justify-content-between">
                            <span><strong class="text-info">[${c.dept}]</strong> ${c.activity} (${c.km} km)</span>
                            <span class="text-warning">Score: ${c.score}</span>
                        </li>
                    `;
                });
                html += `</ul></div>`;
                container.innerHTML = html;
            } else {
                container.innerHTML = `<div class="text-muted small"><i class="fa-solid fa-check-circle text-success me-1"></i> No immediate conflicts or existing demands in this 8km radius. Will be scheduled as independent or anchor block.</div>`;
            }
        } catch (e) {
            console.error(e);
        }
    }

    if (kmStartInput && kmEndInput && corridorSelect) {
        kmStartInput.addEventListener('input', debounce(checkCoLocation, 400));
        kmEndInput.addEventListener('input', debounce(checkCoLocation, 400));
        corridorSelect.addEventListener('change', checkCoLocation);
    }
});

// Helper for CSRF Token in Django
function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

// Simple Toast Notification
function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('globalToastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'globalToastContainer';
        toastContainer.style.position = 'fixed';
        toastContainer.style.bottom = '24px';
        toastContainer.style.right = '24px';
        toastContainer.style.zIndex = '99999';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `alert alert-${type} shadow-lg text-white border-0 py-2 px-3 mb-2 rounded-3 d-flex align-items-center gap-2`;
    toast.style.background = type === 'success' ? '#065f46' : type === 'danger' ? '#991b1b' : '#1e3a8a';
    toast.style.minWidth = '300px';
    toast.innerHTML = `
        <i class="fa-solid ${type === 'success' ? 'fa-check-circle text-success' : type === 'danger' ? 'fa-triangle-exclamation text-danger' : 'fa-info-circle'}"></i>
        <div class="flex-grow-1 small">${message}</div>
        <button type="button" class="btn-close btn-close-white btn-sm" onclick="this.parentElement.remove()"></button>
    `;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, 4500);
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}
