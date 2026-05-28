// Absolute Axis - UI & Navigation Module
const THEMES = ['default', 'gold', 'pink', 'green', 'red', 'purple'];

function updateThemeIcon() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.innerText = document.body.classList.contains('light-mode') ? '🌙' : '☀️';
}

function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    localStorage.setItem('axis-bg-mode', isLight ? 'light' : 'dark');
    updateThemeIcon();
}

function setTheme(theme) {
    THEMES.forEach(t => document.body.classList.remove('theme-' + t));
    document.body.classList.add('theme-' + theme);
    localStorage.setItem('axis-accent-theme', theme);
}

// 路由路徑與視圖映射字典
const ROUTE_MAP = {
    '/introduce': 'intro',
    '/price': 'pricing',
    '/main': 'dashboard',
    '/virtal': 'virtual',
    '/iot': 'smart',
    '/axcloud': 'cloud',
    '/nas': 'nas-mgnt',
    '/axai': 'placeholder',
    '/livedata': 'metrics',
    '/system': 'settings',
    '/idmanage': 'admin'
};

const VIEW_TO_ROUTE = {
    'intro': '/introduce',
    'pricing': '/price',
    'dashboard': '/main',
    'virtual': '/virtal',
    'smart': '/iot',
    'cloud': '/axcloud',
    'nas-mgnt': '/nas',
    'ai': '/axai',
    'placeholder': '/axai',
    'metrics': '/livedata',
    'settings': '/system',
    'admin': '/idmanage'
};

// 暴露至全域供外部存取
window.ROUTE_MAP = ROUTE_MAP;
window.VIEW_TO_ROUTE = VIEW_TO_ROUTE;

function switchView(v, pushHistory = true) {
    // 前端 Route Guard 強化
    const token = localStorage.getItem('axis_token');
    if (!token && !['intro', 'pricing'].includes(v)) {
        console.warn(`Unauthorized attempt to view: ${v}. Redirecting to intro.`);
        v = 'intro';
        setTimeout(() => {
            if (typeof showLoginOverlay === 'function') showLoginOverlay();
        }, 200);
    }

    if (pushHistory) {
        const route = VIEW_TO_ROUTE[v];
        if (route && window.location.pathname !== route) {
            history.pushState(null, '', route);
        }
    }

    if (['ai'].includes(v)) {
        const ts = { 'ai': '核心 AI 助手' };
        const is = { 'ai': '🤖' };
        document.getElementById('ph-title').innerText = ts[v] + " 系統尚未開放";
        document.getElementById('ph-icon').innerText = is[v];
        v = 'placeholder';
    }
    
    // 如果已經在該視圖且已載入完成，則跳過重複載入（除非是手動重新啟動）
    const currentActiveView = document.querySelector('.view-section.active');
    if (currentActiveView && currentActiveView.id === 'view-' + v && v !== 'dashboard') {
        console.log(`Already in view: ${v}, skipping redundant switch.`);
        return;
    }

    document.querySelectorAll('.view-section').forEach(e => e.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(e => e.classList.remove('active'));
    
    const targetView = document.getElementById('view-' + v);
    if (targetView) targetView.classList.add('active');
    
    let nId = 'nav-' + v;
    if (v === 'placeholder') {
        nId = (document.getElementById('ph-icon').innerText === '🏡' ? 'nav-smart' : 'nav-ai');
    }
    
    const n = document.getElementById(nId);
    if (n) n.classList.add('active');

    const titles = {
        'intro': '服務介紹',
        'pricing': '方案定價',
        'dashboard': '戰情總覽',
        'virtual': '虛擬化中心',
        'cloud': '私有雲儲存',
        'nas-mgnt': 'NAS 管理中樞',
        'admin': '帳號管理',
        'settings': '系統設定',
        'metrics': '實時數據分析',
        'multiverse': '多重宇宙',
        'smart': '智慧宅控'
    };
    
    document.getElementById('page-title-text').innerText = titles[v] || document.getElementById('ph-title').innerText.replace(' 系統尚未開放', '');

    // 儲存當前視圖，實現持久化
    localStorage.setItem('axis_current_view', v);

    // 路由行為觸發器
    if (v === 'cloud') { 
        if (typeof loadNASFiles === 'function') {
            const savedPath = localStorage.getItem('nas_current_path') || '';
            loadNASFiles(savedPath); 
        } 
    }
    if (v === 'admin') { if (typeof loadUsers === 'function') loadUsers(); }
    if (v === 'settings') { if (typeof closeSettingPanel === 'function') { closeSettingPanel(); loadSpecs(); } }
    if (v === 'virtual') { 
        if (typeof loadDocker === 'function') loadDocker(); 
        if (typeof loadProxmoxStatus === 'function') loadProxmoxStatus();
        if (typeof loadProxmoxVMs === 'function') loadProxmoxVMs();
    }
    if (v === 'metrics') { if (typeof initCharts === 'function') initCharts(); }
    if (v === 'nas-mgnt') { if (typeof refreshNASHardware === 'function') refreshNASHardware(); }
    if (v === 'multiverse') { if (typeof loadMultiverse === 'function') loadMultiverse(); }
    if (v === 'smart') { if (typeof loadSmart === 'function') loadSmart(); }

    // 收合行動端側邊欄
    if (typeof closeSidebar === 'function') closeSidebar();

    // 觸發視圖切換自定義事件
    document.dispatchEvent(new CustomEvent('view-switched', { detail: { view: v } }));
}

function openSettingPanel(id) {
    document.getElementById('settings-main').style.display = 'none';
    document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(id).classList.add('active');


}

function closeSettingPanel() {
    document.getElementById('settings-main').style.display = 'block';
    document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
    

}

window.toggleAxisPopover = function(e) {
    if (e) e.stopPropagation();
    const p = document.getElementById('user-popover');
    if (p) p.classList.toggle('active');
}

window.addEventListener('click', (e) => {
    // avatar popover
    const avatarBtn = document.getElementById('avatar-btn');
    const popover = document.getElementById('user-popover');
    if (avatarBtn && popover && !avatarBtn.contains(e.target) && !popover.contains(e.target)) {
        popover.classList.remove('active');
    }
    
    // nas new menu
    const newMenuBtn = document.querySelector('[onclick*="toggleNewMenu"]');
    const newMenu = document.getElementById('new-menu');
    if (newMenu && !newMenu.contains(e.target) && (!newMenuBtn || !newMenuBtn.contains(e.target))) {
        newMenu.style.display = 'none';
    }

    // 行動端側邊欄點擊外部收合
    const sidebar = document.querySelector('.sidebar');
    const menuBtn = document.getElementById('menu-btn');
    if (sidebar && sidebar.classList.contains('active') && !sidebar.contains(e.target) && (!menuBtn || !menuBtn.contains(e.target))) {
        sidebar.classList.remove('active');
    }
});

window.toggleNewMenu = function(e) {
    if (e) e.stopPropagation();
    const m = document.getElementById('new-menu');
    if (m) m.style.display = (m.style.display === 'none' ? 'block' : 'none');
}

// 個人設定彈窗觸發器 (Identity Panel Triggers)
window.openProfileEdit = function() {
    const m = document.getElementById('modal-profile');
    if (m) m.style.display = 'flex';
}

window.openAvatarEdit = function() {
    const m = document.getElementById('modal-avatar');
    if (m) m.style.display = 'flex';
}

// 個人設定彈窗觸發器 (Identity Panel Triggers)
window.openProfileEdit = function() {
    const m = document.getElementById('modal-profile');
    if (m) m.style.display = 'flex';
}

window.openAvatarEdit = function() {
    const m = document.getElementById('modal-avatar');
    if (m) m.style.display = 'flex';
}

// Clock logic
setInterval(() => {
    const clock = document.getElementById('clock');
    if (clock) clock.innerText = new Date().toLocaleTimeString('en-GB');
}, 1000);

// Login overlay controls
window.showLoginOverlay = function() {
    const loginOverlay = document.getElementById('login-overlay');
    if (loginOverlay) {
        loginOverlay.style.display = 'flex';
        const userField = document.getElementById('login-user');
        if (userField) userField.focus();
    }
};

window.hideLoginOverlay = function() {
    const loginOverlay = document.getElementById('login-overlay');
    if (loginOverlay) loginOverlay.style.display = 'none';
    
    // 如果未登入且關閉了登入框，強制導向 intro 頁面
    if (!localStorage.getItem('axis_token')) {
        document.body.classList.add('not-logged-in');
        if (typeof switchView === 'function') {
            switchView('intro');
        }
    }
};

window.toggleSidebar = function(e) {
    if (e) e.stopPropagation();
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.classList.toggle('active');
};

window.closeSidebar = function() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.classList.remove('active');
};

// 監聽瀏覽器上一頁與下一頁導覽事件
window.addEventListener('popstate', () => {
    const matchedView = ROUTE_MAP[window.location.pathname];
    if (matchedView) {
        switchView(matchedView, false);
    }
});
