// Absolute Axis - Proxmox Integration Module
async function loadProxmoxStatus() {
    const el = document.getElementById('pve-node-status');
    if (!el) return;

    try {
        const res = await authFetch('/api/proxmox/status');
        if (!res.ok) return;
        const nodes = await res.json();
        
        el.innerHTML = '';
        nodes.forEach(node => {
            const card = document.createElement('div');
            card.className = 'stat-card';
            card.style = "padding: 1.5rem; display: flex; flex-direction: column; gap: 10px;";
            
            const up = node.status === 'online';
            const statusColor = up ? 'var(--success-color)' : 'var(--danger-color)';
            
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:900; color:var(--accent-color); font-size:1.1rem;">🖥️ ${node.name.toUpperCase()}</div>
                    <div style="width:10px; height:10px; border-radius:50%; background:${statusColor}; box-shadow: 0 0 10px ${statusColor};"></div>
                </div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:5px;">PVE HOST NODE</div>
                <div style="display:flex; flex-direction:column; gap:8px; margin-top:5px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
                        <span>CPU Load</span>
                        <span style="font-weight:800;">${node.cpu}%</span>
                    </div>
                    <div class="progress-bar" style="height:6px; background:rgba(255,255,255,0.05);">
                        <div class="progress-fill" style="width:${node.cpu}%; background:linear-gradient(90deg, var(--accent-color), #fff);"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-top:5px;">
                        <span>Memory</span>
                        <span style="font-weight:800;">${node.memory.percent}%</span>
                    </div>
                    <div class="progress-bar" style="height:6px; background:rgba(255,255,255,0.05);">
                        <div class="progress-fill" style="width:${node.memory.percent}%; background:linear-gradient(90deg, #3498db, #fff);"></div>
                    </div>
                </div>
            `;
            el.appendChild(card);
        });
    } catch (e) {
        console.error("Proxmox load error:", e);
    }
}

async function loadProxmoxVMs() {
    const el = document.getElementById('pve-vm-list');
    if (!el) return;

    try {
        const res = await authFetch('/api/proxmox/vms');
        if (!res.ok) return;
        const vms = await res.json();
        
        el.innerHTML = '';
        if (vms.length === 0) {
            el.innerHTML = '<div style="color:var(--text-muted); padding:1rem;">未發現 PVE 虛擬機。</div>';
            return;
        }

        vms.forEach(vm => {
            const up = vm.status === 'running';
            const statusClr = up ? 'var(--success-color)' : 'var(--text-muted)';
            const item = document.createElement('div');
            item.className = 'file-list-item';
            item.style = `display:flex; align-items:center; justify-content:space-between; padding:12px 20px; border-left:4px solid ${statusClr}; margin-bottom:8px;`;
            
            const actionBtn = up ? 
                `<button class="btn btn-outline" style="padding:4px 8px; font-size:0.7rem; color:var(--danger-color);" onclick="sendVMAction(${vm.id}, '${vm.node}', 'shutdown', '${vm.type}')">⏹️ 關機</button>` :
                `<button class="btn btn-outline" style="padding:4px 8px; font-size:0.7rem; color:var(--success-color);" onclick="sendVMAction(${vm.id}, '${vm.node}', 'start', '${vm.type}')">▶️ 啟動</button>`;

            const consoleBtn = `<button class="btn btn-outline" style="padding:4px 8px; font-size:0.7rem; color:var(--accent-color);" onclick="openConsoleModal(${vm.id}, '${vm.node}', '${vm.type}', ${up})">🎛️ 控制台</button>`;

            item.innerHTML = `
                <div style="display:flex; align-items:center; gap:15px;">
                    <div style="font-size:1.5rem;">${vm.type === 'qemu' ? '💻' : '📦'}</div>
                    <div>
                        <div style="font-weight:800; font-size:1rem; color:var(--text-main);">${vm.name}</div>
                        <div style="font-size:0.7rem; color:var(--text-muted); font-family:monospace;">ID: ${vm.id} • ${vm.node} • ${vm.cpu} Core / ${vm.mem}G</div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:0.75rem; font-weight:800; color:${statusClr}; text-transform:uppercase; margin-right:10px;">${vm.status}</span>
                    <div style="display:flex; gap:5px;">
                        ${actionBtn}
                        ${consoleBtn}
                        <button class="btn btn-outline" style="padding:4px 8px; font-size:0.7rem;" onclick="sendVMAction(${vm.id}, '${vm.node}', 'reboot', '${vm.type}')">🔄</button>
                    </div>
                </div>
            `;
            el.appendChild(item);
        });
        
        // 同步載入 VM 帳號列表
        loadVMAccounts();
    } catch (e) {
        console.error("Proxmox VM load error:", e);
    }
}

window.sendVMAction = async function(vmid, node, action, type) {
    try {
        const res = await authFetch(`/api/proxmox/vm/action?vmid=${vmid}&node=${node}&action=${action}&vm_type=${type}`, {
            method: 'POST'
        });
        if (res.ok) {
            console.log(`Action ${action} sent`);
            setTimeout(() => loadProxmoxVMs(), 1000);
        } else {
            const d = await res.json();
            alert(`操作失敗: ${d.detail}`);
        }
    } catch (err) {
        alert("網路錯誤");
    }
}

let currentConsoleVM = null;
let allVMAccounts = [];

// 載入 VM 帳號列表
window.loadVMAccounts = async function() {
    const tbody = document.getElementById('vm-accounts-table-body');
    if (!tbody) return;
    
    try {
        const res = await authFetch('/api/proxmox/vm_users');
        if (!res.ok) {
            tbody.innerHTML = '<tr><td colspan="5" style="padding:20px; text-align:center; color:var(--text-muted);">載入帳號失敗</td></tr>';
            return;
        }
        allVMAccounts = await res.json();
        
        tbody.innerHTML = '';
        if (allVMAccounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="padding:20px; text-align:center; color:var(--text-muted);">尚未建立任何虛擬機帳號</td></tr>';
            return;
        }
        
        allVMAccounts.forEach(acc => {
            const tr = document.createElement('tr');
            tr.style = 'border-bottom:1px solid var(--border-color);';
            tr.innerHTML = `
                <td style="padding:10px; font-weight:800; color:var(--text-main);">${acc.username}</td>
                <td style="padding:10px; font-family:monospace;">${acc.password}</td>
                <td style="padding:10px;">${acc.vmid || '通用'}</td>
                <td style="padding:10px; color:var(--text-muted);">${acc.description || ''}</td>
                <td style="padding:10px; text-align:right;">
                    <button class="btn btn-outline" style="padding:2px 8px; font-size:0.7rem; color:var(--danger-color);" onclick="deleteVMAccount(${acc.id})">刪除</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load VM accounts:", e);
    }
}

// 建立新 VM 帳號
window.createVMAccount = async function() {
    const userVal = document.getElementById('vm-acc-user').value.trim();
    const passVal = document.getElementById('vm-acc-pass').value.trim();
    const vmidVal = document.getElementById('vm-acc-vmid').value.trim();
    const descVal = document.getElementById('vm-acc-desc').value.trim();
    
    if (!userVal || !passVal) {
        if (typeof showToast === 'function') showToast("帳號與密碼為必填項目", "error");
        return;
    }
    
    try {
        const res = await authFetch('/api/proxmox/vm_users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: userVal,
                password: passVal,
                vmid: vmidVal ? parseInt(vmidVal) : null,
                description: descVal || null
            })
        });
        
        if (res.ok) {
            if (typeof showToast === 'function') showToast("虛擬機用戶新增成功", "success");
            document.getElementById('vm-acc-user').value = '';
            document.getElementById('vm-acc-pass').value = '';
            document.getElementById('vm-acc-vmid').value = '';
            document.getElementById('vm-acc-desc').value = '';
            loadVMAccounts();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "新增失敗", "error");
        }
    } catch (err) {
        console.error(err);
    }
}

// 刪除 VM 帳號
window.deleteVMAccount = async function(id) {
    if (!confirm("確定要刪除此虛擬機帳號嗎？")) return;
    try {
        const res = await authFetch(`/api/proxmox/vm_users/${id}`, { method: 'DELETE' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("帳號已成功刪除", "success");
            loadVMAccounts();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "刪除失敗", "error");
        }
    } catch (e) {
        console.error(e);
    }
}

// 開啟控制台 Modal
window.openConsoleModal = async function(vmid, node, type, isRunning) {
    if (!isRunning) {
        if (typeof showToast === 'function') showToast("正在啟動虛擬機，請稍候...", "info");
        const startRes = await authFetch(`/api/proxmox/vm/action?vmid=${vmid}&node=${node}&action=start&vm_type=${type}`, { method: 'POST' });
        if (!startRes.ok) {
            if (typeof showToast === 'function') showToast("自動啟動虛擬機失敗", "error");
            return;
        }
        await new Promise(r => setTimeout(r, 2000));
        loadProxmoxVMs();
    }

    currentConsoleVM = { vmid, node, type };
    
    const select = document.getElementById('vm-console-user-select');
    if (select) {
        select.innerHTML = '<option value="">-- 請選擇帳號 --</option>';
        
        if (allVMAccounts.length === 0) {
            await loadVMAccounts();
        }
        
        const filtered = allVMAccounts.filter(acc => acc.vmid === null || acc.vmid === vmid);
        filtered.forEach(acc => {
            const opt = document.createElement('option');
            opt.value = acc.id;
            opt.innerText = acc.username + (acc.vmid ? ' (專屬)' : ' (通用)');
            select.appendChild(opt);
        });
    }
    
    const disp = document.getElementById('vm-console-credentials-display');
    if (disp) disp.style.display = 'none';

    const modal = document.getElementById('vm-console-modal');
    if (modal) modal.style.display = 'flex';
}

window.closeVMConsoleModal = function() {
    const modal = document.getElementById('vm-console-modal');
    if (modal) modal.style.display = 'none';
    currentConsoleVM = null;
}

// 監聽下拉選單選擇帳號
document.addEventListener('change', (e) => {
    if (e.target && e.target.id === 'vm-console-user-select') {
        const id = parseInt(e.target.value);
        const disp = document.getElementById('vm-console-credentials-display');
        const dispUser = document.getElementById('vm-console-disp-user');
        const dispPass = document.getElementById('vm-console-disp-pass');
        
        if (!id) {
            if (disp) disp.style.display = 'none';
            return;
        }
        
        const acc = allVMAccounts.find(a => a.id === id);
        if (acc && disp && dispUser && dispPass) {
            dispUser.innerText = acc.username;
            dispPass.innerText = acc.password;
            disp.style.display = 'block';
        }
    }
});

window.confirmOpenVMConsole = async function() {
    const select = document.getElementById('vm-console-user-select');
    if (!select || !select.value) {
        if (typeof showToast === 'function') showToast("請先選擇登入帳號", "error");
        return;
    }
    
    if (!currentConsoleVM) return;
    
    const { vmid, node, type } = currentConsoleVM;
    
    try {
        const res = await authFetch(`/api/proxmox/console_url?vmid=${vmid}&node=${node}&vm_type=${type}`);
        if (res.ok) {
            const data = await res.json();
            window.open(data.url, '_blank');
            closeVMConsoleModal();
        } else {
            if (typeof showToast === 'function') showToast("獲取控制台連結失敗", "error");
        }
    } catch (err) {
        console.error(err);
    }
}

