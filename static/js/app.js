/**
 * Absolute Axis - Core Application Entry Point
 * Handles dynamic component loading and system initialization.
 */
const App = {
    components: {
        views: ['intro', 'dashboard', 'virtual', 'smart', 'cloud', 'nas-mgnt', 'metrics', 'admin', 'settings', 'placeholder', 'multiverse'],
        modals: ['profile', 'avatar', 'share', 'preview', 'mkdir', 'deploy-vm', 'admin-edit', 'create-user'],
        overlays: ['popover', 'context-menu']
    },

    async init() {
        console.log("--- INITIALIZING ABSOLUTE AXIS MODULAR SYSTEM ---");
        
        try {
            // 1. Parallel loading of all components
            // 使用 allSettled 避免單一組件 404 導致整體 boot() 不執行
            await Promise.allSettled([
                ...this.components.views.map(v => this.loadComponent(`/static/components/views/${v}.html`, 'main')),
                ...this.components.modals.map(m => this.loadComponent(`/static/components/modals/${m}.html`, 'body')),
                ...this.components.overlays.map(o => this.loadComponent(`/static/components/overlays/${o}.html`, 'body'))
            ]);

            console.log("--- ALL COMPONENTS LOADED SUCCESSFULLY ---");
        } catch (err) {
            console.error("Component load error (non-fatal):", err);
        }

        // 2. 無論組件載入是否全部成功，都必須執行 boot()
        this.boot();
    },

    async loadComponent(url, target) {
        // 強制提升版本號至 v47 以徹底打破組件緩存
        const res = await fetch(`${url}?v=47`);
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
            document.body.classList.remove('not-logged-in');
            const loginOverlay = document.getElementById('login-overlay');
            if (loginOverlay) loginOverlay.style.display = 'none';
            
            // 同步頭像數據 (Sync Avatar across UI)
            const savedAva = localStorage.getItem('axis_avatar');
            const fallbackAva = "https://api.dicebear.com/7.x/avataaars/svg?seed=" + localStorage.getItem('axis_user');
            const finalAva = (savedAva && savedAva.trim() !== "") ? savedAva : fallbackAva;
            
            const topAva = document.getElementById('top-avatar');
            const popAva = document.getElementById('pop-avatar');
            if (topAva) topAva.src = finalAva;
            if (popAva) popAva.src = finalAva;

            const popName = document.getElementById('pop-name');
            const popRole = document.getElementById('pop-role');
            if (popName) popName.innerText = localStorage.getItem('axis_user');
            if (popRole) popRole.innerText = localStorage.getItem('axis_role') || "Member";
            
            const savedView = localStorage.getItem('axis_current_view') || 'dashboard';
            const finalView = (savedView === 'intro') ? 'dashboard' : savedView;
            if (typeof switchView === 'function') switchView(finalView);
            
            if (typeof initCharts === 'function' && finalView === 'dashboard') initCharts();
            
            // Start Metrics Heartbeat (Background)
            if (typeof startPolling === 'function') {
                startPolling();
                // setInterval removed, dashboard.js handles self-scheduling
            }

            // Role-based UI visibility
            const role = localStorage.getItem('axis_role');
            if (role === 'admin' || role === 'Administrator') {
                const navA = document.getElementById('nav-admin');
                if (navA) navA.style.display = 'block';
            }
        } else {
            // 未登入：嘗試顯示介紹首頁，若組件未載入則 fallback 至原始登入 Overlay
            const introView = document.getElementById('view-intro');
            if (introView) {
                document.body.classList.add('not-logged-in');
                const loginOverlay = document.getElementById('login-overlay');
                if (loginOverlay) loginOverlay.style.display = 'none';
                if (typeof switchView === 'function') switchView('intro');
            } else {
                // Fallback：intro.html 尚未載入，回到傳統登入 Overlay
                document.body.classList.remove('not-logged-in');
                const loginOverlay = document.getElementById('login-overlay');
                if (loginOverlay) loginOverlay.style.display = 'flex';
            }
        }
        
        console.log("--- ABSOLUTE AXIS READY ---");
    }
};

// Application Bootstrap
document.addEventListener('DOMContentLoaded', () => App.init());
