// Persistent but non-intrusive PWA install prompt
(function () {
    if (window.__siwesPwaPromptInit) return;
    window.__siwesPwaPromptInit = true;

    const KEY_NEXT = 'siwes_pwa_prompt_next_at';
    const KEY_NEVER = 'siwes_pwa_prompt_never';
    const KEY_INSTALLED = 'siwes_pwa_installed';
    const COOLDOWN_MS = 3 * 24 * 60 * 60 * 1000; // 3 days
    let deferredPrompt = null;

    function isStandalone() {
        return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    }

    function isIOS() {
        return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    }

    function shouldShow() {
        if (isStandalone()) return false;
        if (localStorage.getItem(KEY_NEVER) === '1') return false;
        if (localStorage.getItem(KEY_INSTALLED) === '1') return false;
        const nextAt = parseInt(localStorage.getItem(KEY_NEXT) || '0', 10);
        return Number.isFinite(nextAt) ? Date.now() >= nextAt : true;
    }

    function deferNextPrompt() {
        localStorage.setItem(KEY_NEXT, String(Date.now() + COOLDOWN_MS));
    }

    function ensurePrompt() {
        let root = document.getElementById('siwes-pwa-install');
        if (root) return root;

        root = document.createElement('div');
        root.id = 'siwes-pwa-install';
        root.style.position = 'fixed';
        root.style.left = '50%';
        root.style.bottom = '16px';
        root.style.transform = 'translateX(-50%)';
        root.style.zIndex = '1085';
        root.style.width = 'min(94vw, 420px)';
        root.style.display = 'none';

        root.innerHTML = `
            <div class="card border shadow-sm" style="background: rgba(255,255,255,0.97); backdrop-filter: blur(8px);">
                <div class="card-body p-3">
                    <div class="fw-semibold mb-1">Install SIWES Logbook</div>
                    <div id="siwes-pwa-text" class="text-muted small mb-3">
                        Add this app for faster access and offline support.
                    </div>
                    <div class="d-flex gap-2">
                        <button id="siwes-pwa-install-btn" type="button" class="btn btn-primary btn-sm">Install</button>
                        <button id="siwes-pwa-later-btn" type="button" class="btn btn-light border btn-sm">Not now</button>
                        <button id="siwes-pwa-never-btn" type="button" class="btn btn-link btn-sm text-muted text-decoration-none p-0 ms-auto">Don't remind</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(root);
        return root;
    }

    function showPrompt(opts) {
        if (!shouldShow()) return;
        const root = ensurePrompt();
        const text = document.getElementById('siwes-pwa-text');
        const installBtn = document.getElementById('siwes-pwa-install-btn');
        const laterBtn = document.getElementById('siwes-pwa-later-btn');
        const neverBtn = document.getElementById('siwes-pwa-never-btn');

        if (!root || !text || !installBtn || !laterBtn || !neverBtn) return;

        const ios = !!(opts && opts.ios);
        if (ios) {
            text.textContent = "On iPhone/iPad: tap Share and choose 'Add to Home Screen'.";
            installBtn.classList.add('d-none');
        } else {
            text.textContent = 'Add this app for faster access and offline support.';
            installBtn.classList.remove('d-none');
        }

        root.style.display = 'block';

        installBtn.onclick = async function () {
            if (!deferredPrompt) return;
            try {
                deferredPrompt.prompt();
                const choice = await deferredPrompt.userChoice;
                deferredPrompt = null;
                if (choice && choice.outcome === 'accepted') {
                    localStorage.setItem(KEY_INSTALLED, '1');
                    root.style.display = 'none';
                } else {
                    deferNextPrompt();
                    root.style.display = 'none';
                }
            } catch (_) {
                deferNextPrompt();
                root.style.display = 'none';
            }
        };

        laterBtn.onclick = function () {
            deferNextPrompt();
            root.style.display = 'none';
        };

        neverBtn.onclick = function () {
            localStorage.setItem(KEY_NEVER, '1');
            root.style.display = 'none';
        };
    }

    window.addEventListener('appinstalled', function () {
        localStorage.setItem(KEY_INSTALLED, '1');
        const root = document.getElementById('siwes-pwa-install');
        if (root) root.style.display = 'none';
    });

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        showPrompt({ ios: false });
    });

    document.addEventListener('DOMContentLoaded', function () {
        if (!shouldShow()) return;
        if (isIOS()) {
            showPrompt({ ios: true });
        }
    });
})();

