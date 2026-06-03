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

function renderUsers() {
    const table = document.getElementById('user-table-body');
    if (!table) return;

    const filtered = window.allUsersCache.filter(u => {
        if (currentFilter === 'all') return true;
        const uStatus = u.status || 'Approved';
        return uStatus.toLowerCase() === currentFilter.toLowerCase();
    });

    const statusBadges = {
        'Approved': '<span class="status-badge" style="background:rgba(46, 204, 113, 0.15); color:#2ecc71; padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:800; border:1px solid rgba(46, 204, 113, 0.3); text-transform:uppercase; margin-left:8px;">已核准</span>',
        'Pending': '<span class="status-badge" style="background:rgba(241, 196, 15, 0.15); color:#f1c40f; padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:800; border:1px solid rgba(241, 196, 15, 0.3); text-transform:uppercase; margin-left:8px;">等待中</span>',
        'Rejected': '<span class="status-badge" style="background:rgba(231, 76, 60, 0.15); color:#e74c3c; padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:800; border:1px solid rgba(231, 76, 60, 0.3); text-transform:uppercase; margin-left:8px;">已拒絕</span>'
    };

    table.innerHTML = filtered.map(u => {
        const uStatus = u.status || 'Approved';
        const badgeHtml = statusBadges[uStatus] || `<span class="status-badge" style="background:rgba(255,255,255,0.15); color:#fff; padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:800; margin-left:8px;">${uStatus}</span>`;

        let actionButtons = '';
        if (uStatus === 'Pending') {
            actionButtons = `
                <button class="btn btn-outline" style="padding:4px 10px;font-size:0.75rem;border-color:#2ecc71;color:#2ecc71;margin-right:5px;" onclick="approveUser('${u.username}')">核准</button>
                <button class="btn btn-outline" style="padding:4px 10px;font-size:0.75rem;border-color:#e74c3c;color:#e74c3c;margin-right:5px;" onclick="rejectUser('${u.username}')">拒絕</button>
            `;
        }

        actionButtons += `<button class="btn btn-outline" style="padding:4px 10px;font-size:0.75rem;" onclick="editUser('${u.username}','${u.role}', ${(u.quota_bytes / 1073741824).toFixed(0)})">編輯</button>`;

        const currentUser = localStorage.getItem('axis_user');
        if (u.username !== currentUser) {
            actionButtons += `<button class="btn btn-danger" style="padding:4px 10px;font-size:0.75rem;margin-left:5px;" onclick="deleteUser('${u.username}')">刪除</button>`;
        }

        return `
            <tr style="border-bottom:1px solid var(--border-color);">
                <td style="padding:15px;"><b>${u.username}</b></td>
                <td style="padding:15px; display:flex; align-items:center; gap:8px;">
                    <span class="role-badge ${u.role === 'Administrator' ? 'role-admin' : 'role-member'}">${u.role}</span>
                    ${badgeHtml}
                </td>
                <td style="padding:15px;"><img src="${u.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + u.username}" style="width:28px;height:28px;border-radius:50%;"></td>
                <td style="padding:15px; font-size:0.85rem; color:var(--text-muted);">${(u.quota_bytes / 1073741824).toFixed(1)} GB</td>
                <td style="padding:15px;">${actionButtons}</td>
            </tr>
        `;
    }).join('');
}
window.renderUsers = renderUsers;

function filterUsers(status, btn) {
    currentFilter = status;

    const tabs = document.querySelectorAll('.admin-tab');
    tabs.forEach(t => {
        t.classList.remove('active');
        t.style.background = 'transparent';
        t.style.color = 'var(--text-muted)';
    });

    if (btn) {
        btn.classList.add('active');
        btn.style.background = 'rgba(255,255,255,0.1)';
        btn.style.color = '#fff';
    }

    renderUsers();
}
window.filterUsers = filterUsers;

async function approveUser(username) {
    if (!confirm(`確定要核准使用者 ${username} 的註冊申請嗎？`)) return;
    const res = await authFetch('/api/admin/update_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user: username, status: 'Approved' })
    });
    if (res.ok) {
        if (typeof showToast === 'function') {
            showToast(`已核准使用者 ${username}`, 'success');
        } else {
            alert(`已核准使用者 ${username}`);
        }
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        alert(`操作失敗：${err.detail || '未知錯誤'}`);
    }
}
window.approveUser = approveUser;

async function rejectUser(username) {
    if (!confirm(`確定要拒絕使用者 ${username} 的註冊申請嗎？`)) return;
    const res = await authFetch('/api/admin/update_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_user: username, status: 'Rejected' })
    });
    if (res.ok) {
        if (typeof showToast === 'function') {
            showToast(`已拒絕使用者 ${username}`, 'warning');
        } else {
            alert(`已拒絕使用者 ${username}`);
        }
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        alert(`操作失敗：${err.detail || '未知錯誤'}`);
    }
}
window.rejectUser = rejectUser;


async function confirmCreateUser() {
    const u = document.getElementById('new-user-name').value;
    const p = document.getElementById('new-user-pass').value;
    const r = document.getElementById('new-user-role').value;
    const q = document.getElementById('new-user-quota').value;
    if (!u || !p) return alert("請填寫完整資訊");
    
    const res = await authFetch('/api/admin/create_user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p, role: r, quota_gb: parseInt(q) })
    });
    
    if (res.ok) {
        alert("帳號建立成功！");
        document.getElementById('modal-create-user').style.display = 'none';
        loadUsers();
    } else {
        const err = await res.json();
        alert("建立失敗: " + (err.detail || "未知錯誤"));
    }
}

let editingUser = "";
function editUser(u, r, q) {
    editingUser = u;
    document.getElementById('target-user-name').innerText = u;
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
        alert("變更成功！");
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
        if (data.new_username) {
            localStorage.setItem('axis_user', data.new_username);
            localStorage.setItem('axis_token', data.new_username); 
        }
        location.reload();
    } else {
        alert("修改失敗");
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
        alert("頭像更新成功！");
        location.reload();
    } else {
        alert("更新失敗，請檢查聯網狀態或圖片網址。");
    }
}

async function deleteUser(username) {
    if (!confirm(`警告：確定要永久刪除使用者 ${username} 嗎？此操作將會清除該用戶所有資料與 NAS 儲存空間且無法復原！`)) return;
    const res = await authFetch(`/api/admin/users/${username}`, {
        method: 'DELETE'
    });
    if (res.ok) {
        if (typeof showToast === 'function') {
            showToast(`已成功刪除使用者 ${username}`, 'error');
        } else {
            alert(`已成功刪除使用者 ${username}`);
        }
        loadUsers();
    } else {
        const err = await res.json().catch(() => ({}));
        alert(`刪除失敗：${err.detail || '未知錯誤'}`);
    }
}
window.deleteUser = deleteUser;

