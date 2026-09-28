/**
 * Absolute Axis - DeviceHub 模組（唯讀）
 * 顯示 DeviceHub 的設備、Proxmox 虛擬機與告警。資料由 Axis 後端代理（/api/devicehub/summary），
 * 控制一律連到 DeviceHub 自己的網址（僅 Tailscale 裝置可開）。
 * 所有來自 DeviceHub 的文字都用 textContent 顯示，不插入 HTML。
 */

let _dhTimer = null;

function _dhEl(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (k === 'text') node.textContent = v;
        else if (k === 'style') node.setAttribute('style', v);
        else node.setAttribute(k, v);
    }
    for (const c of children) if (c != null) node.append(c);
    return node;
}

function _dhRow(label, value) {
    return _dhEl('div', { class: 'smart-info-row' },
        _dhEl('span', { class: 'smart-label', text: label }),
        _dhEl('span', { class: 'smart-value', text: value }));
}

function _dhAgo(ts) {
    if (!ts) return '—';
    const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 60) return `${s} 秒前`;
    if (s < 3600) return `${Math.floor(s / 60)} 分鐘前`;
    return `${Math.floor(s / 3600)} 小時前`;
}

const _DH_STATUS = { online: ['在線', '#2ecc71'], offline: ['離線', '#e74c3c'], unknown: ['未知', '#8b949e'] };

function _dhDeviceCard(d) {
    const [label, color] = _DH_STATUS[d.status] || [d.status, '#8b949e'];
    const t = d.telemetry || {};
    const card = _dhEl('div', { class: 'card', style: `border-top: 4px solid ${color};` },
        _dhEl('div', { style: 'display:flex; justify-content:space-between; align-items:baseline; margin-bottom:0.8rem;' },
            _dhEl('span', { style: 'font-size:1.05rem; font-weight:900;', text: d.name }),
            _dhEl('span', { style: `font-size:0.75rem; font-weight:800; color:${color};`, text: `● ${label}` })));
    const rows = _dhEl('div', { style: 'display:flex; flex-direction:column; gap:8px;' });
    rows.append(_dhRow('類型', d.type === 'esp32' ? 'ESP32' : d.type === 'host' ? '電腦' : (d.type || '—')));
    rows.append(_dhRow('最後回報', _dhAgo(d.last_seen)));
    if (typeof t.temp_c === 'number') rows.append(_dhRow('溫度', `${t.temp_c.toFixed(1)} °C`));
    if (typeof t.hum === 'number') rows.append(_dhRow('濕度', `${Math.round(t.hum)} %`));
    if (typeof t.cpu === 'number') rows.append(_dhRow('CPU', `${Math.round(t.cpu)} %`));
    if (typeof t.ram === 'number') rows.append(_dhRow('記憶體', `${Math.round(t.ram)} %`));
    if (d.wdog) {
        rows.append(_dhRow('看門狗', d.wdog.enabled ? '啟用' : '停用'));
        rows.append(_dhRow('伺服器回應', d.wdog.host_alive ? '正常' : '無回應'));
    }
    card.append(rows);
    return card;
}

function _dhGuestCard(g) {
    const running = g.status === 'running';
    const color = running ? '#2ecc71' : '#8b949e';
    const card = _dhEl('div', { class: 'card', style: `border-top: 4px solid ${color};` },
        _dhEl('div', { style: 'display:flex; justify-content:space-between; align-items:baseline; margin-bottom:0.8rem;' },
            _dhEl('span', { style: 'font-size:1.05rem; font-weight:900;', text: g.name || `#${g.vmid}` }),
            _dhEl('span', { style: `font-size:0.75rem; font-weight:800; color:${color};`,
                text: `${g.type === 'lxc' ? 'CT' : 'VM'} ${g.vmid} · ${running ? '執行中' : '已停止'}` })));
    if (running) {
        const rows = _dhEl('div', { style: 'display:flex; flex-direction:column; gap:8px;' });
        rows.append(_dhRow('CPU', `${Math.round((g.cpu || 0) * 100)} %`));
        if (g.maxmem) rows.append(_dhRow('記憶體', `${((g.mem || 0) / 1024 ** 3).toFixed(1)} / ${(g.maxmem / 1024 ** 3).toFixed(1)} GB`));
        card.append(rows);
    }
    return card;
}

function _dhRender(data) {
    const status = document.getElementById('dh-status');
    const devices = document.getElementById('dh-devices');
    const guests = document.getElementById('dh-guests');
    const alerts = document.getElementById('dh-alerts');
    const link = document.getElementById('dh-open');
    if (!status) return;

    if (!data.configured) {
        status.textContent = '尚未設定 DeviceHub（.env 的 DEVICEHUB_TOKEN）';
        return;
    }
    if (data.error) {
        status.textContent = `⚠ ${data.error}（顯示上一次的資料）`;
        return;
    }
    status.textContent = `資料時間：${new Date(data.generated_at * 1000).toLocaleTimeString('zh-TW')}`;

    // 控制只在 DeviceHub：只接受 http(s) 網址
    if (link && /^https?:\/\//.test(data.ui_url || '')) {
        link.href = data.ui_url;
        link.style.display = '';
    }
    devices.replaceChildren(...(data.devices || []).map(_dhDeviceCard));
    const pve = data.proxmox || {};
    guests.replaceChildren(...(pve.enabled ? pve.guests || [] : []).map(_dhGuestCard));
    alerts.replaceChildren(...(data.alerts || []).map((a) => _dhEl('div', { class: 'smart-info-row' },
        _dhEl('span', { class: 'smart-label', text: new Date(a.ts * 1000).toLocaleString('zh-TW', { hour12: false }) }),
        _dhEl('span', { class: 'smart-value', style: 'text-align:right;', text: a.message }))));
    if (!alerts.children.length) alerts.append(_dhEl('div', { class: 'smart-label', text: '目前沒有告警' }));
}

async function loadDeviceHub() {
    const tab = document.getElementById('smart-tab-devicehub');
    if (!tab || tab.style.display === 'none') {  // 只在頁籤可見時刷新
        if (_dhTimer) { clearTimeout(_dhTimer); _dhTimer = null; }
        return;
    }
    try {
        const res = await authFetch('/api/devicehub/summary');
        if (res.ok) _dhRender(await res.json());
    } catch (e) {
        const status = document.getElementById('dh-status');
        if (status) status.textContent = `連線失敗：${e.message}`;
    } finally {
        if (_dhTimer) clearTimeout(_dhTimer);
        _dhTimer = setTimeout(loadDeviceHub, 10000);
    }
}

// 只有管理員看得到這個頁籤（後端也會擋 403）。頁面元件是動態載入的，
// 所以由 loadSmart() 在打開智慧宅控頁時呼叫，而不是在 DOMContentLoaded。
window.dhApplyRole = function () {
    const btn = document.querySelector('.smart-tab-btn[data-tab="devicehub"]');
    const role = localStorage.getItem('axis_role');
    if (btn) btn.style.display = ['admin', 'Administrator'].includes(role) ? '' : 'none';
};
