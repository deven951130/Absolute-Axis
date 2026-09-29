// Absolute Axis - Proxmox Integration Module
// 小工具：建立元素；文字一律 textContent（虛擬機名稱、帳號來自伺服器資料）
function _pveEl(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === 'text') node.textContent = v;
        else if (k === 'class') node.className = v;
        else if (k === 'style') node.setAttribute('style', v);
        else if (k === 'onclick') node.addEventListener('click', v);
        else node.setAttribute(k, v);
    }
    for (const c of children) if (c != null) node.append(c);
    return node;
}

// 圓環（與總覽頁相同：r=20、周長 125.66）
function _pveRing(pct, color, label) {
    const wrap = _pveEl('div', { class: 'ring' });
    const off = 125.66 - (Math.max(0, Math.min(100, pct)) / 100) * 125.66;
    wrap.innerHTML = `<svg viewBox="0 0 48 48" aria-hidden="true"><circle class="ring-bg" cx="24" cy="24" r="20"></circle><circle class="ring-fill" cx="24" cy="24" r="20" style="stroke:${color}; stroke-dashoffset:${off}"></circle></svg>`;
    wrap.append(_pveEl('b', { text: label }));
    return wrap;
}

function _pveUptime(s) {
    if (!s) return '—';
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d ? `${d} 天 ${h} 小時` : h ? `${h} 小時 ${m} 分` : `${m} 分`;
}

async function loadProxmoxStatus() {
    const el = document.getElementById('pve-node-status');
    if (!el) return;

    try {
        const res = await authFetch('/api/proxmox/status');
        if (!res.ok) return;
        const nodes = await res.json();
        const cards = [];
        nodes.forEach((node) => {
            const up = node.status === 'online';
            const mem = node.memory || {};
            const gb = (b) => (b / 1024 ** 3).toFixed(1);
            const statCard = (ring, title, sub) => _pveEl('section', { class: 'widget', style: 'min-height: 140px; flex-direction: row; align-items: center; gap: 16px;' },
                ring, _pveEl('div', {}, _pveEl('div', { class: 'w-muted', style: 'font-size: 13px;', text: title }), _pveEl('div', { style: 'font-size: 15px; font-weight: 600; margin-top: 2px;', text: sub })));
            cards.push(statCard(_pveRing(node.cpu, '#34D17A', `${Math.round(node.cpu)}%`), 'CPU', node.name));
            cards.push(statCard(_pveRing(mem.percent || 0, '#4C8DFF', `${Math.round(mem.percent || 0)}%`), '記憶體',
                mem.total ? `${gb(mem.used)} / ${gb(mem.total)} GB` : '—'));
            cards.push(_pveEl('section', { class: 'widget', style: 'min-height: 140px; justify-content: center; gap: 4px;' },
                _pveEl('div', { class: 'w-muted', style: 'font-size: 13px;', text: `節點 ${node.name}` }),
                _pveEl('div', { style: `display: flex; align-items: center; gap: 8px; font-size: 22px; font-weight: 700;` },
                    _pveEl('span', { style: `width: 10px; height: 10px; border-radius: 50%; background: ${up ? 'var(--success-color)' : 'var(--danger-color)'};` }),
                    up ? '線上' : '離線'),
                _pveEl('div', { class: 'w-muted', style: 'font-size: 14px;', text: `已運作 ${_pveUptime(node.uptime)}` })));
        });
        el.replaceChildren(...cards);
    } catch (e) {
        console.error("Proxmox load error:", e);
    }
}

const _PVE_ICON = {
    qemu: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="7" rx="2"></rect><rect x="3.5" y="13" width="17" height="7" rx="2"></rect><path d="M7.5 7.5h.01M7.5 16.5h.01"></path></svg>',
    lxc: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"></path><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"></path></svg>',
};

async function loadProxmoxVMs() {
    const el = document.getElementById('pve-vm-list');
    if (!el) return;

    try {
        const res = await authFetch('/api/proxmox/vms');
        if (!res.ok) return;
        const vms = await res.json();

        if (vms.length === 0) {
            el.replaceChildren(_pveEl('p', { class: 'w-muted', text: '沒有找到虛擬機。' }));
            return;
        }

        el.replaceChildren(...vms.map((vm) => {
            const up = vm.status === 'running';
            const ico = _pveEl('span', { class: 'vm-ico', style: `background: ${vm.type === 'qemu' ? '#5E5CE6' : '#20A6A6'};` });
            ico.innerHTML = _PVE_ICON[vm.type] || _PVE_ICON.qemu;
            const pill = _pveEl('span', { class: `vm-pill ${up ? 'on' : ''}`, text: up ? '執行中' : (vm.status === 'stopped' ? '已停止' : vm.status) });
            const actions = _pveEl('div', { class: 'vm-actions' });
            if (up) {
                actions.append(
                    _pveEl('button', { type: 'button', class: 'btn btn-outline', text: '關機', onclick: () => sendVMAction(vm.id, vm.node, 'shutdown', vm.type) }),
                    _pveEl('button', { type: 'button', class: 'btn btn-outline', text: '控制台', onclick: () => openConsoleModal(vm.id, vm.node, vm.type, up) }),
                    _pveEl('button', { type: 'button', class: 'btn btn-outline vm-round', 'aria-label': `重新開機 ${vm.name}`, text: '↻', onclick: () => sendVMAction(vm.id, vm.node, 'reboot', vm.type) }));
            } else {
                actions.append(
                    _pveEl('button', { type: 'button', class: 'btn btn-primary', text: '開機', onclick: () => sendVMAction(vm.id, vm.node, 'start', vm.type) }),
                    _pveEl('button', { type: 'button', class: 'btn btn-outline', text: '控制台', onclick: () => openConsoleModal(vm.id, vm.node, vm.type, up) }));
            }
            return _pveEl('article', { class: `widget vm-card ${up ? '' : 'off'}` },
                _pveEl('div', { class: 'vm-top' }, ico, pill),
                _pveEl('div', { class: 'vm-name', text: vm.name }),
                _pveEl('div', { class: 'w-muted vm-meta', text: `${vm.type === 'qemu' ? 'VM' : 'CT'} ${vm.id} · ${vm.cpu} 核心 · ${vm.mem} GB` }),
                actions);
        }));

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
            // 密碼預設遮住，按「顯示」才看得到（避免旁人瞄到）
            const pass = _pveEl('span', { class: 'num', text: '••••••••' });
            let shown = false;
            const toggle = _pveEl('button', { type: 'button', class: 'btn btn-outline', style: 'padding: 3px 10px; font-size: 12px; margin-left: 8px;', text: '顯示',
                onclick: () => { shown = !shown; pass.textContent = shown ? acc.password : '••••••••'; toggle.textContent = shown ? '隱藏' : '顯示'; } });
            const tr = _pveEl('tr', {},
                _pveEl('td', { style: 'font-weight: 600;', text: acc.username }),
                _pveEl('td', {}, pass, toggle),
                _pveEl('td', { text: acc.vmid || '通用' }),
                _pveEl('td', { class: 'w-muted', text: acc.description || '' }),
                _pveEl('td', { style: 'text-align: right;' },
                    _pveEl('button', { type: 'button', class: 'btn btn-danger', style: 'padding: 4px 12px; font-size: 12px;', text: '刪除', onclick: () => deleteVMAccount(acc.id) })));
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
            toastText(typeof data.detail === 'string' ? data.detail : "新增失敗", "error");
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
            toastText(typeof data.detail === 'string' ? data.detail : "刪除失敗", "error");
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

