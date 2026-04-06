// Absolute Axis - Administration Module
async function loadUsers() {
    const res = await authFetch('/api/admin/users');
    if (!res.ok) return;
    const users = await res.json();
    const table = document.getElementById('user-table-body');
    if (!table) return;
    
    table.innerHTML = users.map(u => `
        <tr style="border-bottom:1px solid var(--border-color);">
            <td style="padding:15px;"><b>${u.username}</b></td>
            <td style="padding:15px;"><span class="role-badge ${u.role === 'Administrator' ? 'role-admin' : 'role-member'}">${u.role}</span></td>
            <td style="padding:15px;"><img src="${u.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + u.username}" style="width:28px;height:28px;border-radius:50%;"></td>
            <td style="padding:15px; font-size:0.85rem; color:var(--text-muted);">${(u.quota_bytes / 1073741824).toFixed(1)} GB</td>
            <td style="padding:15px;"><button class="btn btn-outline" style="padding:4px 10px;font-size:0.75rem;" onclick="editUser('${u.username}','${u.role}', ${(u.quota_bytes / 1073741824).toFixed(0)})">編輯</button></td>
        </tr>
    `).join('');
}

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
