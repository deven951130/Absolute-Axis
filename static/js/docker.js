// Absolute Axis - Virtualization (Docker/KVM) Module
function promptDeployVM(internalName, displayName) {
    document.getElementById('vm-os-internal').value = internalName;
    document.getElementById('deploy-vm-os').innerText = displayName;
    document.getElementById('vm-name').value = internalName + "_01";
    document.getElementById('modal-deploy-vm').style.display = 'flex';
}

async function confirmDeployVM() {
    const os = document.getElementById('vm-os-internal').value;
    const name = document.getElementById('vm-name').value;
    const cpu = parseInt(document.getElementById('vm-cpu').value);
    const ram = parseInt(document.getElementById('vm-ram').value);
    
    if(!name || name.includes(" ")) return alert("名稱不得有空白");

    document.getElementById('modal-deploy-vm').style.display = 'none';
    
    try {
        const res = await authFetch('/api/docker/deploy', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({os_internal_name: os, container_name: name, cpu_cores: cpu, ram_gb: ram})
        });
        const d = await res.json();
        if(res.ok) {
            alert(d.message);
            setTimeout(loadDocker, 2000);
        } else alert(d.message || "部署失敗");
    } catch(e) {
        alert("請求出錯");
    }
}

async function controlDocker(id, act){
    await authFetch('/api/docker/control', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({container_id:id,action:act})});
    setTimeout(loadDocker, 1000);
}

function openVNC(ip, port) {
    const url = `http://${window.location.hostname}:${port}`;
    window.open(url, '_blank');
}

async function loadDocker(){
    const r = await authFetch('/api/docker/containers');
    if(!r.ok) return;
    const list = await r.json();
    const el = document.getElementById('docker-list');
    if (!el) return;
    el.innerHTML = '';
    
    if(list.length === 0) {
        el.innerHTML = '<div style="color:var(--text-muted); padding:2rem; width:100%; text-align:center;">無運作中的虛擬機。</div>';
        return;
    }

    list.forEach(c => {
        const up = c.State.toLowerCase() === 'running';
        const statusClr = up ? 'var(--success-color)' : 'var(--text-muted)';
        const item = document.createElement('div');
        item.className = 'file-list-item';
        item.style = `display:flex; align-items:center; justify-content:space-between; padding:15px 25px; border-left:4px solid ${statusClr};`;
        
        const names = c.Names;
        const isHeavyOS = c.Image.includes("dockurr") || c.Image.includes("linuxserver") || c.Image.includes("sickcodes") || c.Image.includes("android");
        
        let vncHtml = "";
        if(up && isHeavyOS && c.vnc_port) {
            vncHtml = `<button class="btn btn-primary" style="padding:6px 12px; font-size:0.8rem; background:var(--success-color); color:#0d1117;" onclick="openVNC('${window.location.hostname}', '${c.vnc_port}')">🖥️ WebVNC 桌面</button>`;
        } else if(up && isHeavyOS) {
            vncHtml = `<span style="font-size:0.75rem; color:var(--text-muted);">正在初始化 WebVNC...</span>`;
        }

        item.innerHTML = `
            <div style="display:flex; align-items:center; gap:18px;">
                <div style="font-size:2rem;">${isHeavyOS ? '📦' : '🐳'}</div>
                <div>
                    <div style="font-weight:800; font-size:1.1rem; color:var(--text-main);">${names}</div>
                    <div style="font-size:0.75rem; color:var(--text-muted); margin-top:5px; font-family:monospace;">${c.Image} • ID: ${c.ID}</div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
                ${vncHtml}
                ${up ? `<button class="btn btn-outline" style="padding:6px 12px; font-size:0.8rem; color:var(--danger-color); border-color:var(--border-color);" onclick="controlDocker('${c.ID}','stop')">■ 停止</button>` 
                     : `<button class="btn btn-outline" style="padding:6px 12px; font-size:0.8rem; color:var(--accent-color); border-color:var(--accent-color);" onclick="controlDocker('${c.ID}','start')">▶ 啟動</button>`}
                <button class="btn btn-outline" style="padding:6px 12px; font-size:0.8rem;" onclick="controlDocker('${c.ID}','restart')">↻ 重啟</button>
                <button class="btn btn-danger" style="padding:6px 12px; font-size:0.8rem;" onclick="controlDocker('${c.ID}','rm -f')">🗑️ 移除</button>
            </div>
        `;
        el.appendChild(item);
    });
}
