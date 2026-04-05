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

function switchView(v) {
    if (['smart', 'ai'].includes(v)) {
        const ts = { 'smart': '智慧宅控', 'ai': '核心 AI 助手' };
        const is = { 'smart': '🏡', 'ai': '🤖' };
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
        'dashboard': '戰情總覽',
        'virtual': '虛擬化中心',
        'cloud': '私有雲儲存',
        'nas-mgnt': 'NAS 管理中樞',
        'admin': '帳號管理',
        'settings': '系統設定',
        'metrics': '實時數據分析'
    };
    
    document.getElementById('page-title-text').innerText = titles[v] || document.getElementById('ph-title').innerText.replace(' 系統尚未開放', '');

    // 儲存當前視圖，實現持久化
    localStorage.setItem('axis_current_view', v);

    // 路由行為觸發器
    if (v === 'cloud') { if (typeof loadNASFiles === 'function') loadNASFiles(''); }
    if (v === 'admin') { if (typeof loadUsers === 'function') loadUsers(); }
    if (v === 'settings') { if (typeof closeSettingPanel === 'function') { closeSettingPanel(); loadSpecs(); } }
    if (v === 'virtual') { if (typeof loadDocker === 'function') loadDocker(); }
    if (v === 'metrics') { if (typeof initCharts === 'function') initCharts(); }
    if (v === 'nas-mgnt') { if (typeof refreshNASHardware === 'function') refreshNASHardware(); }

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
