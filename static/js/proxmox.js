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
            
            item.innerHTML = `
                <div style="display:flex; align-items:center; gap:15px;">
                    <div style="font-size:1.5rem;">${vm.type === 'qemu' ? '💻' : '📦'}</div>
                    <div>
                        <div style="font-weight:800; font-size:1rem; color:var(--text-main);">${vm.name}</div>
                        <div style="font-size:0.7rem; color:var(--text-muted); font-family:monospace;">ID: ${vm.id} • ${vm.node} • ${vm.cpu} Core / ${vm.mem}G</div>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:0.75rem; font-weight:800; color:${statusClr}; text-transform:uppercase;">${vm.status}</span>
                </div>
            `;
            el.appendChild(item);
        });
    } catch (e) {
        console.error("Proxmox VM load error:", e);
    }
}
