/**
 * Absolute Axis - 玻璃介面的小功能（版面：Claude Design「Absolute Axis 版面重設計」）
 * - 頂部日期、總覽頁的問候標題
 * - 側邊欄搜尋（過濾功能選單）
 * - 側邊欄底部的帳號名稱
 * - 主題切換鈕改用線條圖示（取代 emoji）
 * 所有使用者資料都用 textContent 顯示。
 */

const _GLASS_SUN = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"></path></svg>';
const _GLASS_MOON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"></path></svg>';

// 覆寫 ui.js 的 emoji 圖示：亮色時顯示月亮（切到暗色），暗色時顯示太陽（切到亮色）
window.updateThemeIcon = function () {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const light = document.body.classList.contains('light-mode');
    btn.innerHTML = light ? _GLASS_MOON : _GLASS_SUN;
    btn.setAttribute('aria-label', light ? '切換成暗色' : '切換成亮色');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', light ? '#EEF0F5' : '#07080C');
};

function _glassToday() {
    const el = document.getElementById('today-date');
    if (el) el.textContent = new Date().toLocaleDateString('zh-TW', { month: 'long', day: 'numeric', weekday: 'long' });
}

function _glassGreeting() {
    const h = new Date().getHours();
    const word = h < 5 ? '夜深了' : h < 11 ? '早安' : h < 14 ? '午安' : h < 18 ? '下午好' : '晚上好';
    const user = localStorage.getItem('axis_user');
    return user ? `${word}，${user}` : word;
}

function _glassApplyTitle(view) {
    if (view !== 'dashboard') return;
    const t = document.getElementById('page-title-text');
    if (t) t.textContent = _glassGreeting();
}

function _glassProfile() {
    const user = localStorage.getItem('axis_user') || '訪客';
    const role = localStorage.getItem('axis_role');
    const name = document.getElementById('side-user-name');
    const roleEl = document.getElementById('side-user-role');
    const av = document.getElementById('side-avatar');
    if (name) name.textContent = user;
    if (roleEl) roleEl.textContent = role === 'Administrator' || role === 'admin' ? '管理員' : '會員';
    if (av) av.textContent = (user.trim()[0] || 'A').toUpperCase();
}

// 側邊欄搜尋：只過濾「看得到」的功能（被停用或無權限的項目本來就隱藏）
window.filterNav = function (q) {
    const needle = String(q || '').trim().toLowerCase();
    document.querySelectorAll('.sidebar .nav-item').forEach((li) => {
        const label = (li.textContent || '').toLowerCase();
        li.classList.toggle('nav-filtered', needle !== '' && !label.includes(needle));
    });
    document.querySelectorAll('.sidebar .nav-heading').forEach((h) => h.classList.toggle('nav-filtered', needle !== ''));
};

// 手機底部分頁列（index.html #tabbar）：高亮目前頁面；不在四個分頁裡的頁面算「更多」
const _GLASS_TABS = ['dashboard', 'smart', 'virtual', 'cloud'];
function _glassTabbar(view) {
    const target = _GLASS_TABS.includes(view) ? view : 'more';
    document.querySelectorAll('#tabbar .tab').forEach((t) => {
        if (t.dataset.view === target) t.setAttribute('aria-current', 'page');
        else t.removeAttribute('aria-current');
    });
}

document.addEventListener('view-switched', (e) => {
    const view = e.detail && e.detail.view;
    _glassApplyTitle(view);
    _glassTabbar(view);
});

document.addEventListener('DOMContentLoaded', () => {
    _glassToday();
    _glassProfile();
    window.updateThemeIcon();
    const active = document.querySelector('.view-section.active');
    if (active) {
        _glassApplyTitle(active.id.replace('view-', ''));
        _glassTabbar(active.id.replace('view-', ''));
    }
    const brand = document.querySelector('.sidebar .brand');
    if (brand) brand.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') switchView('dashboard'); });
    setInterval(_glassToday, 60000);
});
