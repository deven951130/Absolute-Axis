/**
 * Absolute Axis - NAS Management Frontend Logic
 * Handles real-time hardware status synchronization and SMART monitoring.
 */

async function refreshNASHardware() {
    console.log("--- REFRESHING NAS HARDWARE STATUS ---");
    try {
        const res = await authFetch('/api/system/hardware');
        if (!res.ok) {
            console.warn("Hardware API not ready or access denied.");
            return;
        }
        const d = await res.json();
        
        // 1. Update Physical Disks (sda, sdb)
        d.disks.forEach((disk, i) => {
            const nameEl = document.getElementById(`disk-${i}-name`);
            const statusEl = document.getElementById(`disk-${i}-status`);
            const devEl = document.getElementById(`disk-${i}-dev`);
            const infoEl = document.getElementById(`disk-${i}-info`);
            const barEl = document.getElementById(`disk-${i}-bar`);
            const valEl = document.getElementById(`disk-${i}-val`);
            const tempEl = document.getElementById(`disk-${i}-temp`);

            if (nameEl) nameEl.textContent = disk.name;
            if (statusEl) {
                const ok = disk.status === 'NORMAL';
                statusEl.textContent = ok ? '健康' : `異常（${disk.status}）`;
                statusEl.className = ok ? 'pill ok' : 'pill bad';
            }
            if (devEl) devEl.textContent = `${disk.device} · ${disk.type}`;
            if (infoEl) infoEl.textContent = `容量 ${disk.total_gb} GB · 已用 ${disk.used_gb} GB`;
            if (barEl) {
                barEl.style.width = disk.used_pct + '%';
                barEl.style.background = disk.used_pct > 90 ? 'var(--danger-color)' : 'var(--accent-color)';
            }
            if (valEl) valEl.textContent = disk.used_pct.toFixed(0) + '%';
            // 溫度欄位已在 HTML 中被設定為 display:none 隱藏
            // if (tempEl) {
            //     tempEl.innerText = `溫度: ${disk.temp}°C`;
            //     tempEl.style.color = disk.temp > 50 ? 'var(--danger-color)' : 'var(--text-muted)';
            // }
        });

        // 2. Update Storage Pool / RAID Status
        const rName = document.getElementById('raid-name');
        const rType = document.getElementById('raid-type');
        const rStatus = document.getElementById('raid-status');
        const rBar = document.getElementById('raid-bar');
        
        if (rName) rName.textContent = d.raid.name;
        if (rType) rType.textContent = d.raid.type;
        if (rStatus) {
            const online = d.raid.status === 'ONLINE';
            rStatus.textContent = online ? '運作中' : `異常（${d.raid.status}）`;
            rStatus.className = online ? 'pill ok' : 'pill bad';
        }
        if (rBar) rBar.style.background = d.raid.status === 'ONLINE' ? 'var(--success-color)' : 'var(--danger-color)';
        
        // 3. Storage Allocation Details
        const dCore = document.getElementById('det-core');
        const dUser = document.getElementById('det-user');
        const dDocker = document.getElementById('det-docker');
        
        if (dCore) dCore.textContent = d.details.core;
        if (dUser) dUser.textContent = d.details.user;
        if (dDocker) dDocker.textContent = d.details.docker;

    } catch (e) {
        console.error("NAS Hardware refresh error:", e);
    }
}

// 掛載到全局，供 HTML 按鈕使用
window.refreshNASHardware = refreshNASHardware;

// 初始化與定時刷新
document.addEventListener('view-switched', (e) => {
    if (e.detail.view === 'nas-mgnt') {
        refreshNASHardware();
    }
});

// 每 30 秒自動背景掃描硬體健康
setInterval(() => {
    const nasView = document.getElementById('view-nas-mgnt');
    if (nasView && nasView.classList.contains('active')) {
        refreshNASHardware();
    }
}, 30000);
