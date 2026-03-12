// Lightweight offline resume helper for cached app pages
(function () {
    if (window.__siwesOfflineResumeInit) return;
    window.__siwesOfflineResumeInit = true;

    const KEY_LAST_PATH = 'siwes_last_protected_path';
    const KEY_LAST_ROLE = 'siwes_last_role';
    const KEY_LAST_AUTH_AT = 'siwes_last_auth_at';
    const KEY_LAST_AUTH_NAME = 'siwes_last_auth_name';
    const KEY_LAST_AUTH_EMAIL = 'siwes_last_auth_email';
    const WORKSPACE_CACHE = 'siwes-workspace-v1';

    function isProtectedPath(path) {
        return path.startsWith('/student/') || path.startsWith('/supervisor/');
    }

    function getOfflineLoginDays() {
        const raw = Number(window.__siwesOfflineLoginDays || 7);
        if (!Number.isFinite(raw) || raw < 1) return 7;
        return Math.floor(raw);
    }

    function storeLastPath() {
        const path = window.location.pathname || '/';
        if (!isProtectedPath(path)) return;
        try {
            localStorage.setItem(KEY_LAST_PATH, path + (window.location.search || ''));
            if (path.startsWith('/student/')) localStorage.setItem(KEY_LAST_ROLE, 'student');
            if (path.startsWith('/supervisor/')) localStorage.setItem(KEY_LAST_ROLE, 'supervisor');
        } catch (_) {}
    }

    function getOfflineResumePath() {
        let lastPath = '';
        let role = '';
        try {
            lastPath = localStorage.getItem(KEY_LAST_PATH) || '';
            role = localStorage.getItem(KEY_LAST_ROLE) || '';
        } catch (_) {
            lastPath = '';
            role = '';
        }
        if (lastPath) return lastPath;
        if (role === 'student') return '/student/dashboard';
        if (role === 'supervisor') return '/supervisor/dashboard';
        return '';
    }

    function clearOfflineLease() {
        try {
            localStorage.removeItem(KEY_LAST_AUTH_AT);
            localStorage.removeItem(KEY_LAST_AUTH_NAME);
            localStorage.removeItem(KEY_LAST_AUTH_EMAIL);
            localStorage.removeItem(KEY_LAST_PATH);
            localStorage.removeItem(KEY_LAST_ROLE);
        } catch (_) {}
    }

    function hasValidOfflineLease() {
        const maxDays = getOfflineLoginDays();
        let lastAuth = 0;
        try {
            lastAuth = Number(localStorage.getItem(KEY_LAST_AUTH_AT) || 0);
        } catch (_) {
            lastAuth = 0;
        }
        if (!Number.isFinite(lastAuth) || lastAuth <= 0) return false;
        const ageMs = Date.now() - lastAuth;
        return ageMs <= (maxDays * 24 * 60 * 60 * 1000);
    }

    function recordLastSuccessfulAuthFromPage() {
        const el = document.getElementById('offline-auth-state');
        if (!el) return;
        try {
            localStorage.setItem(KEY_LAST_AUTH_AT, String(Date.now()));
            localStorage.setItem(KEY_LAST_AUTH_NAME, String(el.dataset.name || '').trim());
            localStorage.setItem(KEY_LAST_AUTH_EMAIL, String(el.dataset.email || '').trim());
            const role = String(el.dataset.role || '').trim();
            if (role === 'student' || role === 'supervisor') {
                localStorage.setItem(KEY_LAST_ROLE, role);
            }
        } catch (_) {}
    }

    function renderLoginOfflineResume() {
        const path = window.location.pathname || '/';
        if (path !== '/login') return;
        const params = new URLSearchParams(window.location.search || '');
        if (params.get('logged_out') === '1') {
            clearOfflineLease();
            return;
        }
        if (navigator.onLine) return;

        const lastPath = getOfflineResumePath();
        const leaseValid = hasValidOfflineLease();
        if (!lastPath || !leaseValid) return;

        const form = document.querySelector('form[action="/login"]');
        if (!form) return;
        if (document.getElementById('offline-resume-alert')) return;

        let authName = '';
        let authEmail = '';
        try {
            authName = localStorage.getItem(KEY_LAST_AUTH_NAME) || '';
            authEmail = localStorage.getItem(KEY_LAST_AUTH_EMAIL) || '';
        } catch (_) {
            authName = '';
            authEmail = '';
        }
        const who = authName || authEmail || 'last authenticated user';

        const wrap = document.createElement('div');
        wrap.id = 'offline-resume-alert';
        wrap.className = 'alert alert-warning mt-3';
        wrap.innerHTML = `
            <div class="small mb-2">You're offline. Password login requires internet.</div>
            <div class="small mb-2">Continue as <strong>${who}</strong> using cached workspace.</div>
            <button type="button" class="btn btn-sm btn-outline-dark" id="offline-resume-btn">
                Open cached workspace
            </button>
        `;
        form.appendChild(wrap);

        const btn = document.getElementById('offline-resume-btn');
        if (btn) {
            btn.addEventListener('click', function () {
                window.location.href = lastPath;
            });
        }
    }

    async function prewarmWorkspaceCache() {
        if (!navigator.onLine) return;
        if (!('caches' in window)) return;

        const path = window.location.pathname || '/';
        if (!isProtectedPath(path)) return;

        const routes = path.startsWith('/student/')
            ? ['/student/dashboard', '/student/logbook', '/student/communication', '/student/profile']
            : ['/supervisor/dashboard', '/supervisor/logs', '/supervisor/communication', '/supervisor/geofencing'];

        try {
            const cache = await caches.open(WORKSPACE_CACHE);
            for (const route of routes) {
                try {
                    const res = await fetch(route, {
                        method: 'GET',
                        credentials: 'same-origin',
                        headers: { 'X-Offline-Prewarm': '1' },
                    });
                    if (res && res.ok) {
                        await cache.put(route, res.clone());
                    }
                } catch (_) {}
            }
        } catch (_) {}
    }

    document.addEventListener('DOMContentLoaded', function () {
        recordLastSuccessfulAuthFromPage();
        storeLastPath();
        window.addEventListener('pageshow', storeLastPath);
        window.addEventListener('popstate', storeLastPath);
        document.body.addEventListener('htmx:afterSwap', function () {
            recordLastSuccessfulAuthFromPage();
            storeLastPath();
        });
        renderLoginOfflineResume();
        prewarmWorkspaceCache();
    });
})();
