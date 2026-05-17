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
                        <button class="btn btn-outline" style="padding:4px 8px; font-size:0.7rem;" onclick="sendVMAction(${vm.id}, '${vm.node}', 'reboot', '${vm.type}')">🔄</button>
                    </div>
                </div>
            `;
            el.appendChild(item);
        });
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

window.quickDeployVM = async function(osType) {
    if (!confirm(`確定要快速部署 ${osType} 虛擬機嗎？\n這將在 Fast-Storage 上建立新的磁碟並分配資源。`)) return;

    try {
        const res = await authFetch(`/api/proxmox/deploy?os_type=${osType}`, {
            method: 'POST'
        });
        const data = await res.json();
        
        if (res.ok) {
            alert(`部署成功！\n虛擬機 ID: ${data.vmid}\n${data.message}`);
            loadProxmoxVMs(); // Refresh list
        } else {
            alert(`部署失敗: ${data.detail}`);
        }
    } catch (err) {
        alert("網路錯誤，無法連接伺服器。");
    }
}
