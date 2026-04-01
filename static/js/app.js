/**
 * Absolute Axis - Core Application Entry Point
 * Handles dynamic component loading and system initialization.
 */
const App = {
    components: {
        views: ['dashboard', 'virtual', 'cloud', 'nas-mgnt', 'metrics', 'admin', 'settings', 'placeholder'],
        modals: ['profile', 'avatar', 'share', 'preview', 'mkdir', 'deploy-vm', 'admin-edit', 'create-user'],
        overlays: ['popover', 'context-menu']
    },

    async init() {
        console.log("--- INITIALIZING ABSOLUTE AXIS MODULAR SYSTEM ---");
        
        try {
            // 1. Parallel loading of all components
            await Promise.all([
                ...this.components.views.map(v => this.loadComponent(`/static/components/views/${v}.html`, 'main')),
                ...this.components.modals.map(m => this.loadComponent(`/static/components/modals/${m}.html`, 'body')),
                ...this.components.overlays.map(o => this.loadComponent(`/static/components/overlays/${o}.html`, 'body'))
            ]);

            console.log("--- ALL COMPONENTS LOADED SUCCESSFULLY ---");
            
            // 2. Execute Bootloader logic
            this.boot();
        } catch (err) {
            console.error("Critical error during component initialization:", err);
        }
    },

    async loadComponent(url, target) {
        // 強制加入版本號以打破瀏覽器快取 (Cache Busting)
        const res = await fetch(`${url}?v=12`);
        if (!res.ok) throw new Error(`Failed to load component: ${url}`);
        const html = await res.text();
        const container = (target === 'body') ? document.body : document.querySelector(target);
        if (container) container.insertAdjacentHTML('beforeend', html);
    },

    boot() {
        // Theme Restoration
        const bgMode = localStorage.getItem('axis-bg-mode');
        const accentTheme = localStorage.getItem('axis-accent-theme') || 'default';
        if (bgMode === 'light') document.body.classList.add('light-mode');
        if (typeof setTheme === 'function') setTheme(accentTheme);
        if (typeof updateThemeIcon === 'function') updateThemeIcon();

        // Auth & Navigation
        const token = localStorage.getItem('axis_token');
        if (token) {
            const loginOverlay = document.getElementById('login-overlay');
            if (loginOverlay) loginOverlay.style.display = 'none';
            
            document.getElementById('top-avatar').src = localStorage.getItem('axis_avatar') || "https://api.dicebear.com/7.x/avataaars/svg?seed=" + localStorage.getItem('axis_user');
            document.getElementById('pop-name').innerText = localStorage.getItem('axis_user');
            document.getElementById('pop-role').innerText = localStorage.getItem('axis_role');
            
            if (typeof switchView === 'function') switchView('dashboard');
            if (typeof initCharts === 'function') initCharts();
            
            // Start Metrics Heartbeat (2000ms Polling)
            if (typeof startPolling === 'function') {
                startPolling();
                setInterval(startPolling, 2000);
            }

            // Role-based UI visibility
            const role = localStorage.getItem('axis_role');
            if (role === 'admin' || role === 'Administrator') {
                const navA = document.getElementById('nav-admin');
                if (navA) navA.style.display = 'block';
            }
        } else {
            const loginOverlay = document.getElementById('login-overlay');
            if (loginOverlay) loginOverlay.style.display = 'flex';
        }
        
        console.log("--- ABSOLUTE AXIS READY ---");
    }
};

// Application Bootstrap
document.addEventListener('DOMContentLoaded', () => App.init());
