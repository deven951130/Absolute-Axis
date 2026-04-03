// Absolute Axis - API & Auth Module
let authToken = localStorage.getItem('axis_token');
let myRole = localStorage.getItem('axis_role');

async function authFetch(url, opts = {}) {
    if (!opts.headers) opts.headers = {};
    if (authToken) {
        opts.headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const r = await fetch(url, opts);
    if (r.status === 401) {
        localStorage.clear();
        location.reload();
    }
    return r;
}

async function doLogin() {
    const u = document.getElementById('login-user').value;
    const p = document.getElementById('login-pass').value;
    if (!u || !p) return alert("請填寫帳號密碼");

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
