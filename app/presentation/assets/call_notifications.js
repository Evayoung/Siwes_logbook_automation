// SSE Notification Listener for Call Notifications
(function () {
    let eventSource = null;
    let reconnectTimer = null;
    let currentCallId = null;
    let notificationMenuOpen = false;
    let olderLoadSnapshot = null;
    const recentEventKeys = new Map();

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = String(value || '');
        return div.innerHTML;
    }

    function showToast(message, variant = 'info') {
        const map = {
            success: 'text-bg-success',
            danger: 'text-bg-danger',
            warning: 'text-bg-warning',
            info: 'text-bg-primary',
        };
        let stack = document.getElementById('global-toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.id = 'global-toast-stack';
            stack.className = 'toast-container position-fixed top-0 end-0 p-3';
            stack.style.zIndex = '1080';
            document.body.appendChild(stack);
        }
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center border-0 ${map[variant] || map.info}`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = `
            <div class="d-flex">
	                <div class="toast-body">${escapeHtml(message)}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        stack.appendChild(toastEl);
        if (window.bootstrap && window.bootstrap.Toast) {
            const toast = new window.bootstrap.Toast(toastEl, { delay: 2600 });
            toast.show();
            toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove(), { once: true });
        } else {
            setTimeout(() => toastEl.remove(), 2600);
        }
    }

    function scrollChatToBottom(force = false) {
        const list = document.getElementById('chat-messages-list');
        if (!list) return;
        const nearBottom = (list.scrollHeight - list.scrollTop - list.clientHeight) < 140;
        if (force || nearBottom) {
            list.scrollTop = list.scrollHeight;
        }
    }
    window.scrollChatToBottom = () => scrollChatToBottom(true);

    function isDuplicateEvent(data) {
        try {
            const key = [
                data.type || '',
                data.call_id || '',
                data.status || '',
                data.student_id || '',
                data.sender_id || '',
                data.log_date || '',
                data.message || '',
                data.time || ''
            ].join('|');
            const now = Date.now();
            const last = recentEventKeys.get(key) || 0;
            if ((now - last) < 8000) return true;
            recentEventKeys.set(key, now);
            for (const [k, ts] of recentEventKeys.entries()) {
                if ((now - ts) > 30000) recentEventKeys.delete(k);
            }
        } catch (_) {}
        return false;
    }

    function clearReconnectTimer() {
        if (!reconnectTimer) return;
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    function scheduleSseReconnect() {
        if (!navigator.onLine) return;
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            window.__siwesSseInitialized = false;
            initializeSSE();
        }, 3000);
    }

    function closeSSE() {
        clearReconnectTimer();
        if (eventSource) {
            try { eventSource.close(); } catch (_) {}
        }
        eventSource = null;
        window.eventSource = null;
        window.__siwesSseInitialized = false;
    }

    function initializeSSE() {
        if (!navigator.onLine) return;
        if (window.__siwesSseInitialized) return;
        window.__siwesSseInitialized = true;

        // Connect to SSE stream
        eventSource = new EventSource('/notifications/stream');
        window.eventSource = eventSource;

        eventSource.onopen = function () {
            clearReconnectTimer();
            console.log('[SSE] Connected to notification stream');
        };

        eventSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);
                console.log('[SSE] Received event:', data);
                if (isDuplicateEvent(data)) return;

                // Handle different event types
                switch (data.type) {
                    case 'connected':
                        console.log('[SSE] Connection confirmed for user:', data.user_id);
                        break;

                    case 'call_incoming':
                        handleIncomingCall(data);
                        break;

                    case 'call_cancelled':
                        handleCallCancelled(data);
                        break;

                    case 'call_accepted':
                        handleCallAccepted(data);
                        break;

                    case 'new_message':
                        handleNewMessage(data);
                        break;

                    case 'log_submitted':
                        handleLogSubmitted(data);
                        break;

                    case 'log_reviewed':
                        handleLogReviewed(data);
                        break;
                }
            } catch (error) {
                console.error('[SSE] Error parsing event:', error);
            }
        };

        eventSource.onerror = function (error) {
            console.error('[SSE] Connection error:', error);
            closeSSE();
            scheduleSseReconnect();
        };
    }

    async function refreshNotificationBell() {
        if (!navigator.onLine) return;
        const countEl = document.getElementById('topbar-notification-count');
        const listEl = document.getElementById('topbar-notification-list');
        if (!countEl || !listEl) return;

        try {
            const response = await fetch('/notifications/inbox', { credentials: 'same-origin' });
            if (!response.ok) return;
            const data = await response.json();
            const count = Number(data.count || 0);
            countEl.textContent = String(count);
            countEl.classList.toggle('d-none', count <= 0);

            if (!Array.isArray(data.items) || data.items.length === 0) {
                listEl.innerHTML = '<div class="text-muted small p-2">No notifications yet.</div>';
                return;
            }

            const typeMeta = (type) => {
                switch (type) {
                    case 'message_received':
                        return { label: 'Messages', icon: 'bi-chat-dots', accent: 'text-primary' };
                    case 'call_request':
                        return { label: 'Calls', icon: 'bi-telephone-inbound', accent: 'text-success' };
                    case 'log_verified':
                    case 'log_flagged':
                    case 'log_reviewed':
                        return { label: 'Log Updates', icon: 'bi-journal-check', accent: 'text-warning' };
                    case 'system_announcement':
                        return { label: 'System', icon: 'bi-info-circle', accent: 'text-secondary' };
                    default:
                        return { label: 'Other', icon: 'bi-bell', accent: 'text-secondary' };
                }
            };

            const grouped = {};
            for (const item of data.items) {
                const key = (item.type || 'other');
                if (!grouped[key]) grouped[key] = [];
                grouped[key].push(item);
            }

            const orderedTypes = ['message_received', 'call_request', 'log_verified', 'log_flagged', 'log_reviewed', 'system_announcement', 'other'];
            const sections = [];
            for (const type of orderedTypes) {
                const items = grouped[type];
                if (!items || items.length === 0) continue;
                const meta = typeMeta(type);
                const rows = items.map(item => {
	                    const preview = escapeHtml((item.message || '').slice(0, 80));
	                    const title = escapeHtml(item.title || 'Notification');
	                    const itemTime = escapeHtml(new Date(item.time).toLocaleString());
	                    const href = escapeHtml(String(item.action_url || '#').startsWith('/') ? item.action_url : '#');
	                    return `
	                        <a class="topbar-notification-item" href="${href}">
	                            <div class="d-flex align-items-start gap-2">
	                                <i class="bi ${meta.icon} ${meta.accent} mt-1"></i>
	                                <div class="flex-grow-1">
	                                    <div class="fw-semibold small">${title}</div>
	                                    <div class="small text-muted">${preview}</div>
	                                    <div class="meta mt-1">${itemTime}</div>
	                                </div>
	                            </div>
	                        </a>
	                    `;
                }).join('');
                sections.push(`
                    <div class="topbar-notification-group">
                        <div class="topbar-notification-group-title d-flex align-items-center justify-content-between">
                            <span>${meta.label}</span>
                            <span class="badge bg-light text-dark border">${items.length}</span>
                        </div>
                        ${rows}
                    </div>
                `);
            }

            listEl.innerHTML = sections.join('');
        } catch (error) {
            console.error('[NOTIFICATIONS] Failed to refresh bell:', error);
        }
    }

    function initializeTopbarNotificationUI() {
        const toggleBtn = document.getElementById('topbar-notification-toggle');
        const menu = document.getElementById('topbar-notification-menu');
        const markAllBtn = document.getElementById('topbar-mark-all-read');
        if (!toggleBtn || !menu) return;

        toggleBtn.addEventListener('click', async function (event) {
            event.preventDefault();
            notificationMenuOpen = !notificationMenuOpen;
            menu.classList.toggle('d-none', !notificationMenuOpen);
            if (notificationMenuOpen) {
                await refreshNotificationBell();
            }
        });

        document.addEventListener('click', function (event) {
            if (!notificationMenuOpen) return;
            if (!menu.contains(event.target) && !toggleBtn.contains(event.target)) {
                notificationMenuOpen = false;
                menu.classList.add('d-none');
            }
        });

        if (markAllBtn) {
            markAllBtn.addEventListener('click', async function (event) {
                event.preventDefault();
                try {
                    await fetch('/notifications/mark-all-read', {
                        method: 'POST',
                        credentials: 'same-origin',
                    });
                    await refreshNotificationBell();
                } catch (error) {
                    console.error('[NOTIFICATIONS] Failed to mark read:', error);
                }
            });
        }
    }

    function initializeNetworkBadge() {
        const badge = document.getElementById('topbar-network-badge');
        const textEl = document.getElementById('topbar-network-text');
        if (!badge || !textEl) return;

        const iconHtml = (online) => `<i class="bi ${online ? 'bi-wifi' : 'bi-wifi-off'} me-2"></i>`;
        const updateQueueText = (online) => {
            let queued = 0;
            let enabled = false;
            try {
                queued = Number(localStorage.getItem('siwes_offline_queue_count') || '0');
                enabled = localStorage.getItem('siwes_offline_mode_enabled') === '1';
            } catch (_) {
                queued = 0;
                enabled = false;
            }
            if (online) {
                textEl.textContent = queued > 0 ? `Online - ${queued} queued` : 'Online';
                return;
            }
            if (queued > 0) {
                textEl.textContent = `Offline - ${queued} queued`;
                return;
            }
            textEl.textContent = enabled ? 'Offline - cached mode' : 'Offline';
        };
        const update = () => {
            const online = navigator.onLine;
            badge.classList.toggle('offline', !online);
            badge.querySelector('i')?.remove();
            badge.insertAdjacentHTML('afterbegin', iconHtml(online));
            updateQueueText(online);
        };

        update();
        window.addEventListener('online', update);
        window.addEventListener('offline', update);
        window.addEventListener('siwes-offline-state', update);
    }

    function handleIncomingCall(data) {
        if (!navigator.onLine) return;
        console.log('[CALL] Incoming call from:', data.caller_name);
        refreshNotificationBell();

        // Store call ID for accept/decline actions
        currentCallId = data.call_id;

        // Get modal elements
        const modal = document.getElementById('call-notification-modal');
        const backdrop = document.getElementById('call-notification-backdrop');
        const callerName = document.getElementById('caller-name');
        const callerInitials = document.getElementById('caller-initials');
        const callTypeText = document.getElementById('call-type-text');

        // Update modal content
        callerName.textContent = data.caller_name;

        // Generate initials
        const nameParts = data.caller_name.split(' ');
        const initials = nameParts.map(p => p[0]).join('').substring(0, 2).toUpperCase();
        callerInitials.textContent = initials;

        // Set call type
        const callTypeIcon = data.call_type === 'video' ? 'camera-video' : 'telephone';
        callTypeText.textContent = data.call_type === 'video' ? 'Video Call' : 'Voice Call';

        // Show modal
        modal.style.display = 'block';
        backdrop.style.display = 'block';
        setTimeout(() => {
            modal.classList.add('show');
            backdrop.classList.add('show');
        }, 10);

        // Configure actions dynamically for this call.
        const acceptBtn = document.getElementById('accept-call-btn');
        const declineBtn = document.getElementById('decline-call-btn');
        if (acceptBtn) {
            acceptBtn.removeAttribute('disabled');
            acceptBtn.onclick = () => submitCallAction('accept');
        }
        if (declineBtn) {
            declineBtn.removeAttribute('disabled');
            declineBtn.onclick = () => submitCallAction('decline');
        }

        // Play notification sound (optional)
        playNotificationSound();
    }

    function handleCallCancelled(data) {
        if (!navigator.onLine) return;
        console.log('[CALL] Call cancelled');
        hideCallModal();
        refreshNotificationBell();
    }

    function handleCallAccepted(data) {
        if (!navigator.onLine) return;
        console.log('[CALL] Call accepted, redirecting...');
        window.location.href = data.redirect_url;
    }

    async function submitCallAction(action) {
        if (!currentCallId) return;
        const acceptBtn = document.getElementById('accept-call-btn');
        const declineBtn = document.getElementById('decline-call-btn');
        if (acceptBtn) acceptBtn.setAttribute('disabled', 'disabled');
        if (declineBtn) declineBtn.setAttribute('disabled', 'disabled');

        const endpoint = action === 'accept'
            ? `/api/calls/${currentCallId}/accept`
            : `/api/calls/${currentCallId}/decline`;

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
            });

            let data = {};
            try {
                data = await response.json();
            } catch (_) {}

            if (!response.ok) {
                throw new Error(data.error || `Failed to ${action} call`);
            }

            if (action === 'accept') {
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                    return;
                }
                throw new Error('Call accepted but no redirect URL was returned');
            }

            hideCallModal();
            refreshNotificationBell();
        } catch (error) {
            console.error('[CALL] Action failed:', error);
            showToast(error.message || `Unable to ${action} call`, 'danger');
            if (acceptBtn) acceptBtn.removeAttribute('disabled');
            if (declineBtn) declineBtn.removeAttribute('disabled');
        }
    }

    function handleNewMessage(data) {
        if (!navigator.onLine) return;
        const activeRecipientInput = document.querySelector('input[name="recipient_id"]');
        const activeRecipientId = activeRecipientInput ? activeRecipientInput.value : null;
        const senderId = data.sender_id || null;
        const list = document.getElementById('chat-messages-list');
        if (!list || !activeRecipientId || !senderId || activeRecipientId !== senderId) {
            document.body.dispatchEvent(
                new CustomEvent('new_message_notification', { detail: data })
            );
            refreshNotificationBell();
            return;
        }

        const html = `
            <div class="d-flex justify-content-start mb-3">
                <div class="d-flex flex-column align-items-start">
                    <div class="p-3 bg-light text-dark rounded-3 rounded-bottom-left-0" style="max-width: 80%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
	                        ${escapeHtml(data.text)}
                    </div>
                    <div class="text-muted small mt-1 mx-1" style="font-size: 0.7rem;">${data.time}</div>
                </div>
            </div>
        `;

        list.insertAdjacentHTML('beforeend', html);
        scrollChatToBottom(true);
        refreshNotificationBell();
    }

    function handleLogSubmitted(data) {
        if (!navigator.onLine) return;
        refreshNotificationBell();
        showToast(`${data.student_name || 'A student'} submitted a new log.`, 'info');
        const path = window.location.pathname || '';
        if (navigator.onLine && (path.startsWith('/supervisor/logs') || path.startsWith('/supervisor/dashboard'))) {
            setTimeout(() => window.location.reload(), 600);
        }
    }

    function handleLogReviewed(data) {
        if (!navigator.onLine) return;
        refreshNotificationBell();
        const status = String(data.status || '').toLowerCase();
        if (status === 'verified') showToast('Your log was verified.', 'success');
        else if (status === 'flagged') showToast('Your log was flagged for review.', 'warning');
        else showToast(data.message || 'Your log was reviewed.', 'info');

        const path = window.location.pathname || '';
        if (navigator.onLine && (path.startsWith('/student/dashboard') || path.startsWith('/student/logbook'))) {
            setTimeout(() => window.location.reload(), 600);
        }
    }

    function hideCallModal() {
        const modal = document.getElementById('call-notification-modal');
        const backdrop = document.getElementById('call-notification-backdrop');

        modal.classList.remove('show');
        backdrop.classList.remove('show');

        setTimeout(() => {
            modal.style.display = 'none';
            backdrop.style.display = 'none';
        }, 300);

        currentCallId = null;
    }

    function playNotificationSound() {
        // Create and play a simple notification beep
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.3;

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.2);
        } catch (error) {
            console.log('[AUDIO] Could not play notification sound:', error);
        }
    }

    function bindClientEvents() {
        const logoutForm = document.getElementById('logout-confirm-form');
        const logoutBtn = document.getElementById('logout-confirm-submit');
        const logoutSpinner = document.getElementById('logout-confirm-spinner');
        const logoutModal = document.getElementById('logout-confirm-modal');
        if (logoutForm && logoutBtn) {
            logoutForm.addEventListener('submit', function () {
                logoutBtn.setAttribute('disabled', 'disabled');
                if (logoutSpinner) logoutSpinner.classList.remove('d-none');
            });
        }
        if (logoutModal) {
            logoutModal.addEventListener('hidden.bs.modal', function () {
                if (logoutBtn) logoutBtn.removeAttribute('disabled');
                if (logoutSpinner) logoutSpinner.classList.add('d-none');
            });
        }

        document.body.addEventListener('htmx:beforeRequest', function (event) {
            const elt = event.detail && event.detail.elt;
            if (!elt) return;
            if (elt.id === 'chat-history-sentinel') {
                const list = document.getElementById('chat-messages-list');
                if (!list) return;
                olderLoadSnapshot = {
                    prevHeight: list.scrollHeight,
                    prevTop: list.scrollTop,
                };
            }
        });

        document.body.addEventListener('htmx:afterRequest', function (event) {
            const elt = event.detail && event.detail.elt;
            if (!elt) return;
            if (elt.id === 'chat-history-sentinel') {
                const list = document.getElementById('chat-messages-list');
                if (!list || !olderLoadSnapshot) return;
                const newHeight = list.scrollHeight;
                const delta = newHeight - olderLoadSnapshot.prevHeight;
                if (delta > 0) {
                    list.scrollTop = olderLoadSnapshot.prevTop + delta;
                }
                olderLoadSnapshot = null;
            }
        });

        document.body.addEventListener('call_declined', function () {
            hideCallModal();
        });

        document.body.addEventListener('call_error', function (event) {
            const message = event.detail && event.detail.message
                ? event.detail.message
                : 'Unable to process call action.';
            console.error('[CALL] ' + message);
            showToast(message, 'danger');
        });

        document.body.addEventListener('new_message_notification', function () {
            refreshNotificationBell();
        });

        document.body.addEventListener('log_save_result', function (event) {
            const detail = event && event.detail ? event.detail : {};
            const ok = !!detail.ok;
            const queued = !!detail.queued;
            const message = detail.message || (ok ? 'Log saved.' : 'Failed to save log.');
            showToast(message, ok ? (queued ? 'info' : 'success') : 'danger');
            if (!ok) return;
            const modalEl = document.getElementById('logModal');
            if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
                modal.hide();
            }
            if (queued) return;
            setTimeout(() => window.location.reload(), 700);
        });

        document.body.addEventListener('htmx:afterSwap', function (event) {
            const target = event.detail && event.detail.target;
            if (!target) return;
            if (target.id === 'chat-messages-list') {
                scrollChatToBottom(true);
                return;
            }
            if (target.id === 'student-communication-root' || target.id === 'supervisor-communication-root') {
                setTimeout(() => scrollChatToBottom(true), 30);
            }
        });
    }

    // Startup
    document.addEventListener('DOMContentLoaded', function () {
        bindClientEvents();
        initializeNetworkBadge();
        initializeTopbarNotificationUI();
        refreshNotificationBell();
        // Initialize SSE connection
        initializeSSE();
        
        // Close SSE before any HTMX navigation
        document.body.addEventListener('htmx:beforeNavigate', function () {
            console.log('[SSE] Closing connection before navigation');
            closeSSE();
        });
        
        window.addEventListener('offline', function () {
            closeSSE();
        });
        window.addEventListener('online', function () {
            refreshNotificationBell();
            initializeSSE();
        });
        setTimeout(() => scrollChatToBottom(true), 30);
    });
})();
