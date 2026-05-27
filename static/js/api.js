// Absolute Axis - API & Auth Module
let authToken = localStorage.getItem('axis_token');
let myRole = localStorage.getItem('axis_role');

// ==================== Toast 通知系統 ====================

/**
 * showToast - 顯示右下角浮現通知
 * @param {string} message - 通知訊息
 * @param {'success'|'error'|'warning'|'info'} type - 通知類型
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-msg">${message}</span>
    `;

    container.appendChild(toast);

    // 觸發進場動畫
    requestAnimationFrame(() => toast.classList.add('toast-visible'));

    // 3 秒後自動移除
    setTimeout(() => {
        toast.classList.remove('toast-visible');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 3000);
}

// ==================== 認證 Fetch Wrapper ====================

async function authFetch(url, opts = {}) {
    if (!opts.headers) opts.headers = {};
    if (authToken) {
        opts.headers['Authorization'] = `Bearer ${authToken}`;
    }

    let r;
    try {
        r = await fetch(url, opts);
    } catch (networkErr) {
        showToast('無法連線至伺服器，請確認網路狀態', 'error');
        throw networkErr;
    }

    if (r.status === 401) {
        localStorage.clear();
        location.reload();
        return r;
    }

    if (r.status === 403) {
        showToast('權限不足，此操作需要更高權限', 'warning');
    }

    if (r.status >= 500) {
        let detail = `伺服器錯誤 [${r.status}]`;
        try {
            const errData = await r.clone().json();
            if (errData.detail) detail = `伺服器錯誤：${errData.detail}`;
        } catch (_) {}
        showToast(detail, 'error');
    }

    return r;
}

// ==================== 登入 / 登出 ====================

async function doLogin() {
    const u = document.getElementById('login-user').value;
    const p = document.getElementById('login-pass').value;
    if (!u || !p) return alert('請填寫帳號密碼');

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        });

        if (res.ok) {
            const d = await res.json();
            localStorage.setItem('axis_token', d.token);
            localStorage.setItem('axis_role', d.role);
            localStorage.setItem('axis_user', d.username);
            localStorage.setItem('axis_avatar', d.avatar);
            location.reload();
        } else {
            const errData = await res.json().catch(() => ({}));
            alert(`登入失敗 [${res.status}]：${errData.detail || '身分驗證未通過'}`);
        }
    } catch (e) {
        console.error(e);
        alert(`連線至伺服器失敗：${e.message}`);
    }
}

function doLogout() {
    localStorage.clear();
    location.reload();
}
