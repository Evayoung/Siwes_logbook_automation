// Offline queue + sync for student logbook entries
(function () {
    if (window.__siwesOfflineSyncInit) return;
    window.__siwesOfflineSyncInit = true;

    const DB_NAME = 'siwes_offline_db';
    const DB_VERSION = 1;
    const STORE_NAME = 'pending_logs';

    function getConfigEl() {
        return document.getElementById('offline-sync-config');
    }

    function offlineModeEnabled() {
        const cfg = getConfigEl();
        return !!cfg && String(cfg.dataset.offlineMode || '0') === '1';
    }

    function openDb() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = function () {
                const db = req.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, { keyPath: 'client_uuid' });
                    store.createIndex('queued_at', 'queued_at', { unique: false });
                    store.createIndex('log_date', 'log_date', { unique: false });
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error || new Error('Failed to open IndexedDB'));
        });
    }

    async function getAllQueued() {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readonly');
            const store = tx.objectStore(STORE_NAME);
            const req = store.getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error || new Error('Failed to read queue'));
        });
    }

    async function putQueued(item) {
        const db = await openDb();
        const queued = await getAllQueued();
        const sameDate = queued.find((x) => x.log_date === item.log_date);
        if (sameDate && sameDate.client_uuid !== item.client_uuid) {
            await removeQueued(sameDate.client_uuid);
        }

        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).put(item);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error || new Error('Failed to enqueue log'));
        });
    }

    async function removeQueued(clientUuid) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).delete(clientUuid);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error || new Error('Failed to remove queued log'));
        });
    }

    function setSyncCount(count) {
        const badge = document.getElementById('offline-sync-count');
        if (badge) {
            badge.textContent = String(count);
            badge.classList.toggle('d-none', count <= 0);
        }
        setTopbarOfflineHint(count);
        window.dispatchEvent(new Event('siwes-offline-state'));
    }

    function setTopbarOfflineHint(count) {
        try {
            localStorage.setItem('siwes_offline_queue_count', String(Math.max(0, Number(count) || 0)));
        } catch (_) {}
    }

    function localIsoDate(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function parseDateFromTrigger(trigger) {
        const raw = String(trigger.getAttribute('hx-get') || '');
        const marker = '/student/logbook/day/';
        const idx = raw.indexOf(marker);
        if (idx < 0) return null;
        const token = raw.slice(idx + marker.length).trim();
        if (!token) return null;
        if (token === 'today') return localIsoDate(new Date());
        return token;
    }

    function initOfflineGpsCapture() {
        const latInput = document.getElementById('latitude');
        const lngInput = document.getElementById('longitude');
        const coords = document.getElementById('gps-coords');
        const status = document.getElementById('gps-status');
        const alert = document.getElementById('gps-alert');
        const submit = document.getElementById('submit-btn');
        if (!latInput || !lngInput || !coords || !status || !alert || !submit) return;

        const setErr = (msg) => {
            status.textContent = msg + ' (Log will be submitted without location verification)';
            alert.className = 'alert alert-warning';
            submit.disabled = false;
        };
        if (!navigator.geolocation) {
            setErr('GPS not supported on this device');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                latInput.value = String(position.coords.latitude);
                lngInput.value = String(position.coords.longitude);
                coords.textContent = `${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`;
                status.textContent = 'Location acquired';
                alert.className = 'alert alert-success';
                submit.disabled = false;
            },
            () => setErr('Location unavailable - Please check GPS permission'),
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
    }

    function renderOfflineModalForDate(isoDate) {
        const body = document.getElementById('modal-body-content');
        if (!body) return;

        const todayIso = localIsoDate(new Date());
        if (isoDate > todayIso) {
            body.innerHTML = `
                <div class="alert alert-warning">Sorry future entry not allowed</div>
                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            `;
            return;
        }
        if (isoDate < todayIso) {
            body.innerHTML = `
                <div class="alert alert-warning">Log window passed, please contact your supervisor</div>
                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            `;
            return;
        }

        body.innerHTML = `
            <div id="gps-alert" class="alert alert-info">
                <div class="d-flex align-items-center"><i class="bi bi-geo-alt-fill me-2"></i><span id="gps-status">Detecting location...</span></div>
                <div class="small mt-2">Coordinates: <span id="gps-coords" class="font-monospace">--</span></div>
            </div>
            <form method="post" action="/student/logbook/create" hx-post="/student/logbook/create" hx-target="#modal-body-content" hx-swap="outerHTML" hx-indicator="#log-save-spinner" hx-disabled-elt="#submit-btn">
                <div class="mb-3">
                    <label class="form-label">Date</label>
                    <input type="date" class="form-control" name="log_date" value="${isoDate}" readonly>
                </div>
                <div class="mb-3">
                    <label class="form-label">Activity Description *</label>
                    <textarea name="activity_description" rows="6" maxlength="500" required class="form-control" placeholder="Describe your activities for this day..."></textarea>
                </div>
                <input type="hidden" name="latitude" id="latitude" required>
                <input type="hidden" name="longitude" id="longitude" required>
                <div class="d-flex justify-content-end">
                    <button type="button" class="btn btn-secondary me-2" data-bs-dismiss="modal">Close</button>
                    <button type="submit" class="btn btn-primary" id="submit-btn" disabled>
                        <span class="spinner-border spinner-border-sm me-2 htmx-indicator" id="log-save-spinner" aria-hidden="true"></span>
                        Save Log Entry
                    </button>
                </div>
            </form>
        `;
        initOfflineGpsCapture();
    }

    function attachOfflineDayModalOverride() {
        document.body.addEventListener('click', function (event) {
            if (navigator.onLine || !offlineModeEnabled()) return;
            const trigger = event.target && event.target.closest
                ? event.target.closest('[data-bs-target="#logModal"][hx-get^="/student/logbook/day/"]')
                : null;
            if (!trigger) return;
            const isoDate = parseDateFromTrigger(trigger);
            if (!isoDate) return;

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            renderOfflineModalForDate(isoDate);
            const modalEl = document.getElementById('logModal');
            if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
            }
        }, true);
    }

    async function refreshSyncCount() {
        if (!offlineModeEnabled()) {
            setSyncCount(0);
            return;
        }
        const queued = await getAllQueued();
        setSyncCount(queued.length);
    }

    async function submitQueuedItem(item) {
        const res = await fetch('/student/logbook/sync', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item),
        });
        if (!res.ok) {
            let msg = `sync failed (${res.status})`;
            try {
                const data = await res.json();
                msg = data.error || msg;
            } catch (_) {}
            throw new Error(msg);
        }
        return res.json();
    }

    async function syncQueue() {
        if (!offlineModeEnabled() || !navigator.onLine) return;
        const queued = await getAllQueued();
        if (!queued.length) {
            setSyncCount(0);
            return;
        }

        for (const item of queued) {
            try {
                await submitQueuedItem(item);
                await removeQueued(item.client_uuid);
            } catch (err) {
                console.error('[OFFLINE] sync item failed:', err);
                if (String(err.message || '').includes('403') || String(err.message || '').includes('401')) {
                    break;
                }
            }
        }

        const left = await getAllQueued();
        setSyncCount(left.length);
        if (left.length === 0) {
            document.body.dispatchEvent(
                new CustomEvent('log_save_result', { detail: { ok: true, message: 'Queued logs synced successfully.' } })
            );
        }
    }

    function getActiveLogForm() {
        const modal = document.getElementById('logModal');
        if (!modal) return null;
        const forms = modal.querySelectorAll('form');
        for (const form of forms) {
            if (form.getAttribute('action') === '/student/logbook/create' || form.getAttribute('hx-post') === '/student/logbook/create') {
                return form;
            }
        }
        return null;
    }

    function randomId() {
        if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
        return 'offline-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    }

    async function queueCurrentForm(form) {
        const fd = new FormData(form);
        const logDate = String(fd.get('log_date') || '').trim();
        const activityDescription = String(fd.get('activity_description') || '').trim();
        
        const latRaw = fd.get('latitude');
        const lngRaw = fd.get('longitude');
        const latitude = (latRaw && latRaw.trim() !== '') ? Number(latRaw) : null;
        const longitude = (lngRaw && lngRaw.trim() !== '') ? Number(lngRaw) : null;

        if (!logDate || !activityDescription) {
            throw new Error('Missing required fields for offline queue.');
        }
        if (latitude !== null && Number.isNaN(latitude)) {
            throw new Error('Invalid latitude coordinate.');
        }
        if (longitude !== null && Number.isNaN(longitude)) {
            throw new Error('Invalid longitude coordinate.');
        }

        const payload = {
            client_uuid: randomId(),
            log_date: logDate,
            activity_description: activityDescription,
            latitude: latitude,
            longitude: longitude,
            queued_at: new Date().toISOString(),
        };

        await putQueued(payload);
        await refreshSyncCount();
    }

    function attachOfflineSubmitInterceptor() {
        document.body.addEventListener(
            'submit',
            async function (event) {
                const form = event.target;
                if (!form || form.tagName !== 'FORM') return;
                const isLogCreate = form.getAttribute('action') === '/student/logbook/create' || form.getAttribute('hx-post') === '/student/logbook/create';
                if (!isLogCreate) return;

                if (!offlineModeEnabled() || navigator.onLine) return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                try {
                    const submit = form.querySelector('[type="submit"]');
                    if (submit) submit.setAttribute('disabled', 'disabled');
                    await queueCurrentForm(form);
                    const modalEl = document.getElementById('logModal');
                    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                        window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
                    }
                    document.body.dispatchEvent(
                        new CustomEvent('log_save_result', { detail: { ok: true, queued: true, message: 'No internet. Log queued and will sync automatically.' } })
                    );
                } catch (err) {
                    document.body.dispatchEvent(
                        new CustomEvent('log_save_result', { detail: { ok: false, message: String(err.message || err) } })
                    );
                } finally {
                    const submit = form.querySelector('[type="submit"]');
                    if (submit) submit.removeAttribute('disabled');
                }
            },
            true
        );
    }

    function attachSyncButton() {
        const btn = document.getElementById('offline-sync-btn');
        if (!btn) return;
        btn.addEventListener('click', async function () {
            btn.setAttribute('disabled', 'disabled');
            try {
                await syncQueue();
            } finally {
                btn.removeAttribute('disabled');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', async function () {
        const cfg = getConfigEl();
        if (!cfg) return;
        try {
            localStorage.setItem('siwes_offline_mode_enabled', offlineModeEnabled() ? '1' : '0');
        } catch (_) {}
        attachOfflineDayModalOverride();
        attachOfflineSubmitInterceptor();
        attachSyncButton();
        await refreshSyncCount();
        if (navigator.onLine) await syncQueue();
        window.addEventListener('offline', async () => {
            await refreshSyncCount();
        });
        window.addEventListener('online', () => {
            syncQueue().catch((e) => console.error('[OFFLINE] auto-sync failed:', e));
        });
    });

    document.body.addEventListener('htmx:afterSwap', async function (event) {
        const target = event.detail && event.detail.target;
        if (!target) return;
        if (target.id === 'modal-body-content' || target.id === 'weeks-container' || target.id === 'student-communication-root') {
            await refreshSyncCount();
        }
    });
})();
