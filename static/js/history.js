/**
 * Absolute Axis - 智慧宅控「歷史」頁籤：DeviceHub 的真實溫濕度與電腦負載紀錄
 * （DeviceHub repo docs/spec/integration-api.md §3.1a、history.md；後端代理 /api/devicehub/history/*）
 * 圖表：純 SVG（平均線＋最小～最大範圍帶），滑過顯示數值。只給管理員。
 */

const HIST = { device: null, field: null, hours: 24, fields: [], loading: false };
const HIST_META = {
    temp_c: { label: '溫度', unit: '°C', color: '#FF9F43', digits: 1 },
    hum: { label: '濕度', unit: '%', color: '#4C8DFF', digits: 0 },
    cpu: { label: 'CPU', unit: '%', color: '#34D17A', digits: 0 },
    ram: { label: '記憶體', unit: '%', color: '#8C8AF5', digits: 0 },
    disk: { label: '磁碟', unit: '%', color: '#5AB0F5', digits: 0 },
    rssi: { label: 'WiFi', unit: 'dBm', color: '#3CC8C8', digits: 0 },
};
const HIST_ORDER = ['temp_c', 'hum', 'cpu', 'ram', 'disk', 'rssi'];
const SVG_NS = 'http://www.w3.org/2000/svg';

function _histIsAdmin() {
    return ['admin', 'Administrator'].includes(localStorage.getItem('axis_role'));
}

function _histSvg(tag, attrs) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
}

function _histFmt(v, field) {
    const m = HIST_META[field];
    return `${v.toFixed(m.digits)}${m.unit === '°C' ? '°' : ' ' + m.unit}`;
}

function _histTime(t, hours) {
    const d = new Date(t * 1000);
    if (hours <= 24) return d.toLocaleTimeString('zh-TW', { hour12: false, hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) + (hours <= 168 ? ' ' + d.getHours() + '時' : '');
}

async function _histDevices() {
    let devices = (typeof DH !== 'undefined' && DH.data && DH.data.devices) ? DH.data.devices : null;
    if (!devices) {
        const r = await authFetch('/api/devicehub/summary');
        if (!r.ok) return [];
        const d = await r.json();
        devices = d.devices || [];
    }
    return devices;
}

async function loadSmartHistory() {
    const panel = document.getElementById('hist-panel');
    const note = document.getElementById('hist-admin-only');
    if (!panel) return;
    const admin = _histIsAdmin();
    panel.hidden = !admin;
    note.hidden = admin;
    if (!admin) return;

    const devices = await _histDevices();
    const sel = document.getElementById('hist-device');
    if (!HIST.device) {
        const server = devices.find((d) => d.wdog) || devices.find((d) => d.type === 'esp32') || devices[0];
        HIST.device = server ? server.id : null;
    }
    sel.replaceChildren(...devices.map((d) => {
        const o = document.createElement('option');
        o.value = d.id;
        o.textContent = d.name === d.id ? d.id : `${d.name}（${d.id}）`;
        o.selected = d.id === HIST.device;
        return o;
    }));
    if (!HIST.device) { _histRender(null); return; }
    await _histLoadFields();
}

async function _histLoadFields() {
    const r = await authFetch(`/api/devicehub/history/${encodeURIComponent(HIST.device)}/fields`);
    const data = r.ok ? await r.json() : { ok: false };
    HIST.fields = data.ok ? HIST_ORDER.filter((f) => (data.fields || []).includes(f)) : [];
    if (!HIST.fields.includes(HIST.field)) HIST.field = HIST.fields[0] || null;
    const box = document.getElementById('hist-fields');
    box.replaceChildren(...HIST.fields.map((f) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = HIST_META[f].label;
        b.setAttribute('aria-pressed', String(f === HIST.field));
        b.addEventListener('click', () => { HIST.field = f; _histLoadFields(); });
        return b;
    }));
    await _histLoadData();
}

async function _histLoadData() {
    if (!HIST.field) { _histRender(null); return; }
    if (HIST.loading) return;
    HIST.loading = true;
    try {
        const url = `/api/devicehub/history/${encodeURIComponent(HIST.device)}?field=${HIST.field}&hours=${HIST.hours}`;
        const r = await authFetch(url);
        const data = r.ok ? await r.json() : { ok: false };
        _histRender(data.ok ? data : null);
    } finally {
        HIST.loading = false;
    }
}

function _histRender(data) {
    const svg = document.getElementById('hist-svg');
    const empty = document.getElementById('hist-empty');
    const now = document.getElementById('hist-now');
    const stats = document.getElementById('hist-stats');
    const tip = document.getElementById('hist-tip');
    tip.hidden = true;
    svg.replaceChildren();
    const pts = data && data.points ? data.points : [];
    empty.hidden = pts.length > 0;
    if (!pts.length) { now.textContent = '—'; stats.textContent = ''; return; }

    const field = data.field;
    const meta = HIST_META[field];
    const last = pts[pts.length - 1];
    now.textContent = _histFmt(last.avg, field);
    now.style.color = meta.color;
    const avg = pts.reduce((s, p) => s + p.avg, 0) / pts.length;
    const lo = Math.min(...pts.map((p) => p.min));
    const hi = Math.max(...pts.map((p) => p.max));
    stats.textContent = `平均 ${_histFmt(avg, field)} · 最低 ${_histFmt(lo, field)} · 最高 ${_histFmt(hi, field)}`;

    const W = svg.clientWidth || 800, H = 280, L = 44, R = 12, T = 12, B = 28;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const t0 = Date.now() / 1000 - data.hours * 3600, t1 = Date.now() / 1000;
    const pad = (hi - lo) * 0.15 || 1;
    const y0 = lo - pad, y1 = hi + pad;
    const X = (t) => L + (t - t0) / (t1 - t0) * (W - L - R);
    const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);

    const grid = getComputedStyle(document.body).getPropertyValue('--border-color').trim() || 'rgba(128,128,128,.2)';
    const muted = getComputedStyle(document.body).getPropertyValue('--text-muted').trim() || '#888';
    for (let i = 0; i <= 3; i++) {
        const v = y0 + (y1 - y0) * i / 3, y = Y(v);
        svg.append(_histSvg('line', { x1: L, x2: W - R, y1: y, y2: y, stroke: grid, 'stroke-width': 1 }));
        const lab = _histSvg('text', { x: L - 8, y: y + 4, 'text-anchor': 'end', fill: muted, 'font-size': 11 });
        lab.textContent = v.toFixed(meta.digits);
        svg.append(lab);
    }
    for (let i = 0; i <= 4; i++) {
        const t = t0 + (t1 - t0) * i / 4;
        const lab = _histSvg('text', { x: X(t), y: H - 8, 'text-anchor': i === 0 ? 'start' : i === 4 ? 'end' : 'middle', fill: muted, 'font-size': 11 });
        lab.textContent = i === 4 ? '現在' : _histTime(t, data.hours);
        svg.append(lab);
    }

    // 連續的點畫成一段；超過兩個桶沒有資料就斷開
    const gap = data.bucket_s * 2.5;
    const segs = [];
    let cur = [];
    pts.forEach((p, i) => {
        if (i && p.t - pts[i - 1].t > gap) { segs.push(cur); cur = []; }
        cur.push(p);
    });
    segs.push(cur);
    for (const s of segs) {
        if (s.length > 1) {
            const band = s.map((p) => `${X(p.t)},${Y(p.max)}`).concat(s.slice().reverse().map((p) => `${X(p.t)},${Y(p.min)}`)).join(' ');
            svg.append(_histSvg('polygon', { points: band, fill: meta.color, 'fill-opacity': 0.16 }));
        }
        svg.append(_histSvg('polyline', { points: s.map((p) => `${X(p.t)},${Y(p.avg)}`).join(' '), fill: 'none', stroke: meta.color, 'stroke-width': 2.2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    }
    const cursor = _histSvg('line', { y1: T, y2: H - B, stroke: muted, 'stroke-width': 1, 'stroke-dasharray': '3 3', visibility: 'hidden' });
    const dot = _histSvg('circle', { r: 4.5, fill: meta.color, stroke: 'white', 'stroke-width': 2, visibility: 'hidden' });
    svg.append(cursor, dot);

    svg.onmousemove = (e) => {
        const rect = svg.getBoundingClientRect();
        const x = (e.clientX - rect.left) * (W / rect.width);
        let best = pts[0];
        for (const p of pts) if (Math.abs(X(p.t) - x) < Math.abs(X(best.t) - x)) best = p;
        const px = X(best.t), py = Y(best.avg);
        cursor.setAttribute('x1', px); cursor.setAttribute('x2', px); cursor.setAttribute('visibility', 'visible');
        dot.setAttribute('cx', px); dot.setAttribute('cy', py); dot.setAttribute('visibility', 'visible');
        tip.textContent = `${new Date(best.t * 1000).toLocaleString('zh-TW', { hour12: false, month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}　${_histFmt(best.avg, field)}（${_histFmt(best.min, field)}～${_histFmt(best.max, field)}）`;
        tip.hidden = false;
        tip.style.left = `${Math.min(Math.max(px * rect.width / W, 90), rect.width - 90)}px`;
    };
    svg.onmouseleave = () => { cursor.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; };
}

document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'hist-device') { HIST.device = e.target.value; _histLoadFields(); }
    });
    document.addEventListener('click', (e) => {
        const b = e.target.closest ? e.target.closest('#hist-range button') : null;
        if (!b) return;
        HIST.hours = Number(b.dataset.hours);
        document.querySelectorAll('#hist-range button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        _histLoadData();
    });
    window.addEventListener('resize', () => {
        const tab = document.getElementById('smart-tab-data');
        if (tab && tab.style.display !== 'none' && HIST.field) _histLoadData();
    });
});
