// Absolute Axis - Administration Module
window.allUsersCache = [];
let currentFilter = 'all';

async function loadUsers() {
    const res = await authFetch('/api/admin/users');
    if (!res.ok) return;
    window.allUsersCache = await res.json();
    renderUsers();
}
window.loadUsers = loadUsers;

const _ADMIN_STATUS = {
    Approved: ['ok', '已核准'], Pending: ['warn', '等待中'], Rejected: ['bad', '已拒絕'],
};

// 帳號名稱來自註冊表單（任何人都能申請）：一律 textContent＋事件綁定，不插入 HTML（見 app/naming.py）
function renderUsers() {
    const list = document.getElementById('user-table-body');
    if (!list) return;
    const users = window.allUsersCache || [];
    const pending = users.filter((u) => (u.status || 'Approved') === 'Pending').length;
    const count = document.getElementById('admin-pending-count');
    if (count) { count.textContent = String(pending); count.hidden = pending === 0; }

    const filtered = users.filter((u) => currentFilter === 'all'
        || (u.status || 'Approved').toLowerCase() === currentFilter.toLowerCase());
    if (!filtered.length) {
        list.replaceChildren(h('div', { class: 'ios-row static' },
            h('span', { class: 'ios-label ios-muted', text: currentFilter === 'Pending' ? '沒有等待核准的申請。' : '沒有符合的成員。' })));
        return;
    }
    const me = localStorage.getItem('axis_user');
    list.replaceChildren(...filtered.map((u) => {
        const status = u.status || 'Approved';
        const [tone, label] = _ADMIN_STATUS[status] || ['muted', status];
        const isAdmin = u.role === 'Administrator';
        const quotaGb = Math.round((u.quota_bytes || 0) / 1073741824);
        const ava = h('img', { class: 'row-avatar', alt: '' });
        ava.src = u.avatar || ('https://api.dicebear.com/7.x/avataaars/svg?seed=' + encodeURIComponent(u.username));
        const actions = h('span', { class: 'row-actions' });
        if (status === 'Pending') {
            actions.append(
                h('button', { type: 'button', class: 'btn btn-primary btn-sm', text: '核准', onclick: () => approveUser(u.username) }),
                h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: '拒絕', onclick: () => rejectUser(u.username) }));
        }
        actions.append(h('button', { type: 'button', class: 'btn btn-outline btn-sm', text: '編輯',
            onclick: () => editUser(u.username, u.role, quotaGb) }));
        if (u.username !== me) {
            actions.append(h('button', { type: 'button', class: 'btn btn-danger btn-sm', text: '刪除', onclick: () => deleteUser(u.username) }));
        }
        return h('div', { class: 'ios-row static user-row' },
            ava,
            h('span', { class: 'row-main' },
                h('b', { text: u.username }),
                h('span', { text: `${isAdmin ? '管理員' : '會員'} · 儲存空間 ${((u.quota_bytes || 0) / 1073741824).toFixed(1)} GB` })),
            h('span', { class: `pill ${tone}`, text: label }),
            actions);
    }));
}
window.renderUsers = renderUsers;

function filterUsers(status, btn) {
    currentFilter = status;
    document.querySelectorAll('.admin-tab').forEach((t) =>
        t.setAttribute('aria-pressed', String(t === btn || t.dataset.filter === status)));
    renderUsers();
}
window.filterUsers = filterUsers;

async function _adminUpdate(username, status, okText, tone) {
    const res = await authFetch('/api/admin/update_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user: username, status })
    });
    if (res.ok) {
        toastText(`${okText}「${username}」`, tone);
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        toastText(`操作失敗：${err.detail || '未知錯誤'}`, 'error');
    }
}

async function approveUser(username) {
    if (!(await axisAsk({ title: `核准「${username}」？`, message: '核准後對方就能登入 Absolute Axis。', ok: '核准' }))) return;
    await _adminUpdate(username, 'Approved', '已核准', 'success');
}
window.approveUser = approveUser;

async function rejectUser(username) {
    if (!(await axisAsk({ title: `拒絕「${username}」的申請？`, ok: '拒絕', danger: true }))) return;
    await _adminUpdate(username, 'Rejected', '已拒絕', 'warning');
}
window.rejectUser = rejectUser;


async function confirmCreateUser() {
    const u = document.getElementById('new-user-name').value;
    const p = document.getElementById('new-user-pass').value;
    const r = document.getElementById('new-user-role').value;
    const q = document.getElementById('new-user-quota').value;
    if (!u || !p) return toastText("請填寫帳號與密碼", "error");
    
    const res = await authFetch('/api/admin/create_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p, role: r, quota_gb: parseInt(q) })
    });
    
    if (res.ok) {
        toastText("帳號已建立", "success");
        document.getElementById('modal-create-user').style.display = 'none';
        loadUsers();
    } else {
        const err = await res.json();
        toastText("建立失敗：" + (err.detail || "未知錯誤"), "error");
    }
}

let editingUser = "";
function editUser(u, r, q) {
    editingUser = u;
    document.getElementById('target-user-name').textContent = u;
    document.getElementById('admin-user-role').value = r;
    document.getElementById('admin-user-quota').value = q || 1;
    document.getElementById('modal-admin-edit').style.display = 'flex';
}

async function confirmAdminEdit() {
    const p = document.getElementById('admin-user-pass').value;
    const r = document.getElementById('admin-user-role').value;
    const q = document.getElementById('admin-user-quota').value;
    const res = await authFetch('/api/admin/update_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user: editingUser, new_pass: p, new_role: r, quota_gb: parseInt(q) })
    });
    if (res.ok) {
        toastText("變更已儲存", "success");
        document.getElementById('modal-admin-edit').style.display = 'none';
        loadUsers();
    }
}

async function saveProfile() {
    const name = document.getElementById('edit-name').value;
    const pass = document.getElementById('edit-pass').value;
    const res = await authFetch('/api/user/update_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: name, new_pass: pass })
    });
    if (res.ok) {
        const data = await res.json();
        if (data.new_username && data.new_username !== localStorage.getItem('axis_user')) {
            // 登入憑證綁舊名稱：改名後請用新名稱重新登入（以前這裡把名稱寫進 axis_token，等於默默登出）
            localStorage.removeItem('axis_token');
            localStorage.setItem('axis_user', data.new_username);
            toastText("名稱已更新，請用新名稱重新登入", "success");
            setTimeout(() => location.reload(), 1200);
            return;
        }
        location.reload();
    } else {
        const err = await res.json().catch(() => ({}));
        toastText("修改失敗：" + (err.detail || "未知錯誤"), "error");
    }
}

window.saveAvatar = async function() {
    const ava = document.getElementById('edit-ava').value.trim();
    const res = await authFetch('/api/user/update_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ avatar: ava })
    });
    
    if (res.ok) {
        // 核心修正：不論是否為空，皆同步 localStorage 確保快取一致性
        localStorage.setItem('axis_avatar', ava);
        toastText("頭像已更新", "success");
        location.reload();
    } else {
        toastText("更新失敗，請檢查網路或圖片網址", "error");
    }
}

async function deleteUser(username) {
    if (!(await axisAsk({ title: `永久刪除「${username}」？`, ok: '刪除', danger: true,
        message: '會清除這個成員的所有資料與 NAS 儲存空間，無法復原。' }))) return;
    const res = await authFetch(`/api/admin/users/${encodeURIComponent(username)}`, {
        method: 'DELETE'
    });
    if (res.ok) {
        toastText(`已刪除「${username}」`, 'success');
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        toastText(`刪除失敗：${err.detail || '未知錯誤'}`, 'error');
    }
}
window.deleteUser = deleteUser;

