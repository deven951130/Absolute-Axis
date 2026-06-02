/**
 * Absolute Axis - Core Application Entry Point
 * Handles dynamic component loading and system initialization.
 */
const App = {
    components: {
        views: ['intro', 'pricing', 'dashboard', 'virtual', 'smart', 'cloud', 'nas-mgnt', 'metrics', 'admin', 'settings', 'placeholder', 'multiverse', 'gigs', 'opensource', 'feedback'],
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
        let ver = 'dev';
        try {
            const cssLink = document.querySelector('link[rel="stylesheet"]');
            if (cssLink && cssLink.href) {
                // 使用 window.location.origin 作為 base URL 避免相對路徑拋錯
                const urlObj = new URL(cssLink.href, window.location.origin);
                ver = urlObj.searchParams.get('v') || 'dev';
            }
        } catch (e) {
            console.warn("Failed to parse CSS version, falling back to 'dev':", e);
        }

        const res = await fetch(`${url}?v=${ver}`);
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
            
            // 路由解析：優先使用當前網址列的路徑 (window.location.pathname)
            const currentPath = window.location.pathname;
            let finalView = window.ROUTE_MAP ? window.ROUTE_MAP[currentPath] : null;
            
            if (!finalView) {
                // 若無效或為 '/'，預設導向 /main (dashboard 視圖)
                finalView = 'dashboard';
            }
            
            // 權限防禦：限制普通成員存取 idmanage (admin) 視圖
            const role = localStorage.getItem('axis_role');
            if (finalView === 'admin' && role !== 'Administrator') {
                finalView = 'dashboard';
            }
            
            if (typeof switchView === 'function') switchView(finalView, true);
            
            if (typeof initCharts === 'function' && finalView === 'dashboard') initCharts();
            
            // Start Metrics Heartbeat (Background)
            if (typeof startPolling === 'function') {
                startPolling();
            }

            // Role-based UI visibility
            if (role === 'Administrator') {
                const navA = document.getElementById('nav-admin');
                if (navA) navA.style.display = 'block';
            }

            // 更新介紹頁面/定價頁面/接案平台導覽列已登入狀態
            document.querySelectorAll('.intro-logged-out-actions').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.intro-logged-in-actions').forEach(el => el.style.display = 'flex');
            document.querySelectorAll('.intro-avatar-img').forEach(el => el.src = finalAva);
        } else {
            // 未登入：只允許訪問 /introduce 與 /price 頁面，其餘強制跳轉
            const currentPath = window.location.pathname;
            let finalView = window.ROUTE_MAP ? window.ROUTE_MAP[currentPath] : null;
            
            if (finalView !== 'intro' && finalView !== 'pricing') {
                finalView = 'intro';
            }
            
            document.body.classList.add('not-logged-in');
            const loginOverlay = document.getElementById('login-overlay');
            if (loginOverlay) loginOverlay.style.display = 'none';

            // 更新介紹頁面/定價頁面/接案平台導覽列未登入狀態
            document.querySelectorAll('.intro-logged-out-actions').forEach(el => el.style.display = 'flex');
            document.querySelectorAll('.intro-logged-in-actions').forEach(el => el.style.display = 'none');
            
            if (typeof switchView === 'function') switchView(finalView, false);
            
            // 若為未登入狀態且嘗試開啟後台，重導向至 /introduce 並開啟登入遮罩
            if (currentPath !== '/introduce' && currentPath !== '/price') {
                history.replaceState(null, '', '/introduce');
                setTimeout(() => {
                    if (typeof showLoginOverlay === 'function') showLoginOverlay();
                }, 300);
            }
        }
        
        console.log("--- ABSOLUTE AXIS READY ---");
    }
};

// Application Bootstrap
document.addEventListener('DOMContentLoaded', () => App.init());
