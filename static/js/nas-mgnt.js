/**
 * Absolute Axis - NAS 管理
 * GET /api/system/hardware：硬碟卡片有幾顆畫幾張、SMART 重點屬性、儲存池（mdadm／zfs／btrfs）。
 * 所有 API 給的文字都用 textContent 放進 DOM（不用 innerHTML）。
 */

const NAS_DISK_STATUS = {
    OK: ['健康', 'pill ok'],
    WARNING: ['注意', 'pill warn'],
    FAILING: ['異常', 'pill bad'],
    STANDBY: ['休眠中', 'pill info'],
    UNKNOWN: ['無法讀取', 'pill'],
};

const NAS_POOL_STATUS = {
    ONLINE: ['運作中', 'pill ok'],
    REBUILDING: ['重建中', 'pill warn'],
    DEGRADED: ['降級', 'pill bad'],
    INACTIVE: ['未啟用', 'pill bad'],
    UNKNOWN: ['狀態不明', 'pill'],
};

const NAS_DISK_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="13" width="17" height="7" rx="2"></rect><path d="M5.5 13l2.5-8h8l2.5 8M16.5 16.5h.01"></path></svg>';

function nasEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined && text !== null) el.textContent = text;
    return el;
}

function nasPill(map, status) {
    const [label, cls] = map[status] || [status || '—', 'pill bad'];
    return nasEl('span', cls, label);
}

function nasSmartRow(label, value, bad) {
    const row = nasEl('div', 'nas-smart-row');
    row.appendChild(nasEl('span', 'w-muted', label));
    row.appendChild(nasEl('b', bad ? 'nas-bad' : '', value));
    return row;
}

function nasDiskCard(disk) {
    const card = nasEl('section', 'widget nas-disk');
    card.setAttribute('aria-label', `${disk.name}（${disk.device}）`);

    const cap = nasEl('p', 'w-cap');
    cap.style.color = disk.type === 'HDD' ? '#8E8E96' : '#2E9BF0';
    cap.innerHTML = NAS_DISK_ICON;   // 固定的圖示，沒有 API 資料
    cap.appendChild(nasEl('span', '', [disk.device, disk.type || '類型不明', disk.transport ? disk.transport.toUpperCase() : null].filter(Boolean).join(' · ')));
    card.appendChild(cap);

    const top = nasEl('div', 'nas-disk-top');
    top.appendChild(nasEl('h3', 'nas-disk-name', disk.name));
    top.appendChild(nasPill(NAS_DISK_STATUS, disk.status));
    card.appendChild(top);

    const big = nasEl('div', 'nas-big');
    const hasUsage = typeof disk.used_pct === 'number';
    big.appendChild(nasEl('b', 'w-big', hasUsage ? `${disk.used_pct.toFixed(0)}%` : '—'));
    big.appendChild(nasEl('span', 'w-muted', hasUsage ? '已使用' : '用量不明'));
    card.appendChild(big);

    const bar = nasEl('div', 'w-bar');
    const fill = nasEl('div');
    fill.style.width = (hasUsage ? Math.min(100, disk.used_pct) : 0) + '%';
    fill.style.background = hasUsage && disk.used_pct > 90 ? 'var(--danger-color)' : 'var(--accent-color)';
    bar.appendChild(fill);
    card.appendChild(bar);

    card.appendChild(nasEl('p', 'w-muted nas-info',
        hasUsage ? `容量 ${disk.total_gb} GB · 已用 ${disk.used_gb} GB` : `容量 ${disk.total_gb} GB`));

    if (disk.standby) {
        card.appendChild(nasEl('p', 'w-muted nas-note', '硬碟休眠中：為了不把它叫醒，這次沒有讀取 SMART。'));
    } else if (disk.smart) {
        const s = disk.smart;
        const rows = nasEl('div', 'nas-smart');
        const fmt = (v, unit) => (v === null || v === undefined) ? '—' : `${v.toLocaleString()}${unit}`;
        rows.appendChild(nasSmartRow('溫度', fmt(s.temp, '°C'), s.temp > 55));
        rows.appendChild(nasSmartRow('通電時數', fmt(s.power_on_hours, ' 小時')));
        if (s.reallocated !== null && s.reallocated !== undefined) rows.appendChild(nasSmartRow('重新配置磁區', fmt(s.reallocated, ''), s.reallocated > 0));
        if (s.pending !== null && s.pending !== undefined) rows.appendChild(nasSmartRow('待處理磁區', fmt(s.pending, ''), s.pending > 0));
        if (disk.type === 'SSD' || (s.life_left !== null && s.life_left !== undefined)) rows.appendChild(nasSmartRow('SSD 剩餘壽命', fmt(s.life_left, '%'), s.life_left !== null && s.life_left < 10));
        card.appendChild(rows);
    }
    if (disk.smart_note) card.appendChild(nasEl('p', 'w-muted nas-note', disk.smart_note));
    if (disk.usage_note) card.appendChild(nasEl('p', 'w-muted nas-note', disk.usage_note));
    return card;
}

function nasRenderPools(pools) {
    const box = document.getElementById('nas-pools');
    if (!box) return;
    box.replaceChildren();
    if (!pools || pools.length === 0) {
        const row = nasEl('div', 'nas-pool-row');
        const text = nasEl('div', 'nas-pool-text');
        text.appendChild(nasEl('h3', 'nas-disk-name', '未使用 RAID'));
        text.appendChild(nasEl('p', 'w-muted', '沒有偵測到 mdadm、ZFS 或多顆硬碟的 btrfs；每顆硬碟各自獨立。'));
        row.appendChild(text);
        box.appendChild(row);
        return;
    }
    pools.forEach(p => {
        const row = nasEl('div', 'nas-pool-row nas-pool-item');
        const text = nasEl('div', 'nas-pool-text');
        text.appendChild(nasEl('h3', 'nas-disk-name', p.name));
        const kind = { mdadm: '軟體 RAID（mdadm）', zfs: 'ZFS', btrfs: 'btrfs' }[p.kind] || p.kind;
        const desc = [kind, p.level !== p.kind ? p.level : null, p.devices && p.devices.length ? `成員：${p.devices.join('、')}` : null].filter(Boolean).join(' · ');
        text.appendChild(nasEl('p', 'w-muted', desc));
        if (p.note) text.appendChild(nasEl('p', 'w-muted nas-note', p.note));
        row.appendChild(text);
        row.appendChild(nasPill(NAS_POOL_STATUS, p.status));
        box.appendChild(row);
    });
}

async function refreshNASHardware() {
    try {
        const res = await authFetch('/api/system/hardware');
        if (!res.ok) {
            console.warn("Hardware API not ready or access denied.");
            return;
        }
        const d = await res.json();

        // 1. 硬碟卡片：有幾顆畫幾張
        const disksBox = document.getElementById('nas-disks');
        if (disksBox) {
            disksBox.replaceChildren();
            if (d.disks.length === 0) {
                const empty = nasEl('section', 'widget nas-disk');
                empty.appendChild(nasEl('p', 'w-muted nas-info', d.disks_error || '沒有偵測到硬碟。'));
                disksBox.appendChild(empty);
            }
            d.disks.forEach(disk => disksBox.appendChild(nasDiskCard(disk)));
        }
        const note = document.getElementById('nas-container-note');
        if (note) note.hidden = !(d.in_container && d.disks.some(x => x.hidden_partitions > 0));

        // 2. 儲存池
        nasRenderPools(d.pools);

        // 3. 空間用途
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set('det-core', d.details.core);
        set('det-user', d.details.user);
        set('det-docker', d.details.docker || '無法取得');
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
