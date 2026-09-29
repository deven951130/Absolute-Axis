/**
 * Absolute Axis - 系統設定（iOS「設定」風格：個人卡片＋分組清單；settings.html）
 * 面板切換沿用 ui.js 的 openSettingPanel()／closeSettingPanel()；主題沿用 toggleTheme()／setTheme()。
 * 使用者資料一律用 textContent／屬性設定，不插入 HTML。
 */

function _setRoleLabel(role) {
    return role === 'Administrator' || role === 'admin' ? '管理員' : '會員';
}

function _setProfileCard() {
    const user = localStorage.getItem('axis_user') || '訪客';
    const name = document.getElementById('set-name');
    const role = document.getElementById('set-role');
    const img = document.getElementById('set-avatar');
    if (name) name.textContent = user;
    if (role) role.textContent = `${_setRoleLabel(localStorage.getItem('axis_role'))} · 帳號、密碼與頭像`;
    if (img) {
        const saved = (localStorage.getItem('axis_avatar') || '').trim();
        img.src = saved || 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + encodeURIComponent(user);
    }
}

// 讓「外觀」分段控制、強調色色票、主畫面的「深色／淺色」文字跟目前狀態一致
function _setSyncAppearance() {
    const light = document.body.classList.contains('light-mode');
    document.querySelectorAll('#panel-theme .ios-seg button').forEach((b) =>
        b.setAttribute('aria-pressed', String((b.dataset.mode === 'light') === light)));
    const accent = localStorage.getItem('axis-accent-theme') || 'default';
    document.querySelectorAll('#panel-theme .ios-swatch').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.theme === accent)));
    const v = document.getElementById('set-theme-value');
    if (v) v.textContent = light ? '淺色' : '深色';
}

window.setAppearance = function (mode) {
    const light = document.body.classList.contains('light-mode');
    if ((mode === 'light') !== light && typeof toggleTheme === 'function') toggleTheme();
    if (typeof window.updateThemeIcon === 'function') window.updateThemeIcon();
    _setSyncAppearance();
};

window.pickAccent = function (theme) {
    if (typeof setTheme === 'function') setTheme(theme);
    _setSyncAppearance();
};

document.addEventListener('view-switched', (e) => {
    if (!e.detail || e.detail.view !== 'settings') return;
    _setProfileCard();
    _setSyncAppearance();
});

document.addEventListener('DOMContentLoaded', () => {
    // 右上角的主題鈕或其他頁面改了 body 的 class 時，設定頁也跟著更新
    new MutationObserver(_setSyncAppearance).observe(document.body, { attributes: true, attributeFilter: ['class'] });
});
