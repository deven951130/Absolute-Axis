/**
 * Absolute Axis - DeviceHub 模組（智慧宅控 → 首頁，只給管理員）
 *
 * 伺服器電源、設備（桌機／筆電／ESP32）、Proxmox 虛擬機與告警。資料與控制都經 Axis 後端代理
 * （/api/devicehub/*，app/routers/devicehub.py），DeviceHub 的 token 不會進瀏覽器。
 * 規格：DeviceHub repo docs/spec/integration-api.md v0.2、architecture AD-10。
 *
 * - 所有來自 DeviceHub 的文字（設備名稱、告警訊息）只用 textContent 顯示；
 *   showToast() 會插入 HTML，所以傳給它的名稱一律先跳脫。
 * - 危險操作用頁內 <dialog> 確認（NFR-04），不用原生 confirm()：某些內嵌瀏覽器會擋掉它，
 *   危險操作就被默默取消。
 */

const DH = { data: null, controls: null, loading: false, busy: new Set() };

const DH_ACTION_LABELS = {
    'ping': '測試連線',
    'pwrbtn.press': '短按電源鍵',
    'pwrbtn.hold': '長按強制關機',
    'sys.reboot': '重新啟動',
    'host.shutdown': '關機',
    'host.restart': '重新開機',
    'host.sleep': '睡眠',
    'wake': '喚醒',
    'pve.start': '開機', 'pve.shutdown': '關機', 'pve.reboot': '重新開機', 'pve.stop': '強制停止',
};

const DH_RESULT_LABELS = {
    ok: '成功', error: '失敗', expired: '已過期', unsupported: '不支援',
    timeout: '逾時（設備沒有回應）', running: '執行中（Proxmox 仍在處理）',
};

const DH_ERROR_LABELS = {
    control_not_configured: '尚未設定控制 token（.env 的 DEVICEHUB_CONTROL_TOKEN）',
    unreachable: 'DeviceHub 無法連線',
    unauthorized: 'DeviceHub 拒絕了 Axis 的 token',
    forbidden: 'DeviceHub 不接受來自這台主機的控制',
    not_allowed: '這個操作只能在 DeviceHub 網頁做',
    rate_limited: '操作太頻繁，請 10 分鐘後再試',
    bad_operator: '帳號名稱格式不符',
    bad_request: '請求格式錯誤',
    device_offline: '設備離線',
    unknown_device: '找不到設備',
    unsupported_for_device: '此設備不支援這個指令',
    confirm_required: '需要確認',
    publish_failed: 'DeviceHub 的 MQTT 未連線，指令沒送出',
    time_not_synced: '設備尚未校時',
    no_mac: 'DeviceHub 不知道這台電腦的網卡 MAC',
    wol_unavailable: 'DeviceHub 無法送出喚醒封包',
    self_protected: 'DeviceHub 所在的容器不能從這裡關閉',
    unknown_guest: '找不到這台虛擬機',
    pve_error: 'Proxmox 回報錯誤',
    not_configured: 'DeviceHub 尚未設定 Proxmox',
};

// 伺服器電源鍵的說明：Axis 和 DeviceHub 都跑在這台伺服器上
const DH_POWER_WARN = {
    pressOn: '伺服器正在運作。短按電源鍵會讓 Proxmox 開始正常關機，所有虛擬機都會一起關閉——'
        + '包括 Axis 自己和 DeviceHub，這個網站會跟著斷線。之後要開機只能用 Blynk App 或到現場按電源鍵。',
    pressOff: 'DeviceHub 偵測不到伺服器。短按電源鍵通常會讓它開機；如果它其實還開著，則會開始關機。',
    hold: '長按 8 秒會強制切斷伺服器電源，等同拔插頭：執行中的虛擬機可能遺失資料，Axis 也會立刻斷線。\n'
        + '只在伺服器卡死、短按沒有反應時使用。',
};

// ---------- 小工具 ----------

function _dhEl(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === 'text') node.textContent = v;
        else if (k === 'class') node.className = v;
        else if (k === 'onclick') node.addEventListener('click', v);
        else if (v === true) node.setAttribute(k, '');
        else node.setAttribute(k, v);
    }
    for (const c of children) if (c != null) node.append(c);
    return node;
}

function _dhEsc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function _dhAgo(ts) {
    if (!ts) return '—';
    const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 60) return `${s} 秒前`;
    if (s < 3600) return `${Math.floor(s / 60)} 分鐘前`;
    if (s < 86400) return `${Math.floor(s / 3600)} 小時前`;
    return `${Math.floor(s / 86400)} 天前`;
}

function _dhClock(ts) {
    return new Date(ts * 1000).toLocaleTimeString('zh-TW', { hour12: false });
}

function _dhStamp(ts) {
    const d = new Date(ts * 1000);
    const today = new Date().toDateString() === d.toDateString();
    return today ? d.toLocaleTimeString('zh-TW', { hour12: false, hour: '2-digit', minute: '2-digit' })
        : d.toLocaleString('zh-TW', { hour12: false, month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function _dhUptime(s) {
    if (typeof s !== 'number' || s <= 0) return null;
    if (s < 3600) return `${Math.floor(s / 60)} 分`;
    if (s < 86400) return `${Math.floor(s / 3600)} 小時`;
    return `${Math.floor(s / 86400)} 天`;
}

function _dhIsAdmin() {
    return ['admin', 'Administrator'].includes(localStorage.getItem('axis_role'));
}

function _dhVisible() {
    const view = document.querySelector('.view-section.active');
    const tab = document.getElementById('smart-tab-home');
    return view && view.id === 'view-smart' && tab && tab.style.display !== 'none';
}

function _dhErrorText(code) {
    return DH_ERROR_LABELS[code] || code || '未知錯誤';
}

// ---------- 確認視窗 ----------

function _dhAsk(title, message, { ok = '確定', danger = false } = {}) {
    const dlg = document.getElementById('dh-dialog');
    // 對話框放在智慧宅控頁裡；從其他頁（例如總覽）開啟時先移到 body，否則會被隱藏的頁面擋住
    if (dlg && dlg.parentElement !== document.body) document.body.appendChild(dlg);
    if (!dlg || typeof dlg.showModal !== 'function') {
        return Promise.resolve(window.confirm(`${title}\n\n${message}`));
    }
    document.getElementById('dh-dialog-title').textContent = title;
    document.getElementById('dh-dialog-msg').textContent = message;
    const okBtn = document.getElementById('dh-dialog-ok');
    const cancelBtn = document.getElementById('dh-dialog-cancel');
    okBtn.textContent = ok;
    okBtn.className = danger ? 'dh-btn danger-solid' : 'dh-btn primary';
    return new Promise((resolve) => {
        const done = (v) => {
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancel);
            dlg.removeEventListener('cancel', onCancel);
            if (dlg.open) dlg.close();
            resolve(v);
        };
        const onOk = () => done(true);
        const onCancel = (e) => { if (e) e.preventDefault(); done(false); };
        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancel);
        dlg.addEventListener('cancel', onCancel);
        dlg.showModal();
        cancelBtn.focus();  // 危險操作預設停在「取消」
    });
}

// ---------- 控制 ----------

async function _dhRun(key, label, targetName, url, body) {
    if (DH.busy.has(key)) return;
    DH.busy.add(key);
    _dhRender();
    try {
        const res = await authFetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}),
        });
        const out = res.ok ? await res.json() : { ok: false, error: `http_${res.status}` };
        const who = `「${_dhEsc(targetName)}」${_dhEsc(label)}`;
        if (!out.ok) {
            showToast(`${who}：${_dhEsc(_dhErrorText(out.error))}`, 'error');
        } else if (out.result === 'ok' || out.result === 'running') {
            showToast(`${who}：${DH_RESULT_LABELS[out.result]}`, 'success');
        } else {
            const extra = out.error ? `（${_dhEsc(_dhErrorText(out.error))}）` : '';
            showToast(`${who}：${_dhEsc(DH_RESULT_LABELS[out.result] || out.result)}${extra}`, 'warning');
        }
    } catch (e) {
        showToast(`${_dhEsc(label)}：連線失敗`, 'error');
    } finally {
        DH.busy.delete(key);
        loadDeviceHub(true);
        loadDeviceHubDashboard(true);
    }
}

async function _dhCommand(d, action, { warn = null, label = null } = {}) {
    const name = label || DH_ACTION_LABELS[action] || action;
    const spec = _dhDeviceActions(d.id).find((a) => a.action === action);
    const danger = !!(spec && spec.danger);
    if (danger) {
        const msg = warn || `確定要對「${d.name}」執行「${name}」嗎？`;
        if (!await _dhAsk(`${name}：${d.name}`, msg, { ok: name, danger: action.endsWith('.hold') || action === 'host.shutdown' || action === 'sys.reboot' })) return;
    }
    await _dhRun(`${d.id}:${action}`, name, d.name, `/api/devicehub/devices/${encodeURIComponent(d.id)}/commands`,
        { action, params: {}, confirm: danger });
}

async function _dhWake(d, via = null) {
    const label = via ? `經 ${via} 喚醒` : '喚醒';
    await _dhRun(`${d.id}:wake`, label, d.name, `/api/devicehub/devices/${encodeURIComponent(d.id)}/wake`,
        via ? { via } : {});
}

async function _dhPower(g, action) {
    const name = DH_ACTION_LABELS[`pve.${action}`];
    const title = `${name}：${g.name || g.vmid}`;
    if (action !== 'start') {
        const kind = g.type === 'lxc' ? '容器' : '虛擬機';
        let msg = {
            shutdown: `要讓${kind}「${g.name}」正常關機嗎？`,
            reboot: `要讓${kind}「${g.name}」重新開機嗎？`,
            stop: `強制停止等同拔掉「${g.name}」的電源，未存檔的資料會遺失。確定嗎？`,
        }[action];
        if (/axis/i.test(g.name || '')) msg += '\n\n這是 Axis 自己所在的虛擬機：執行後這個網站會中斷。';
        if (!await _dhAsk(title, msg, { ok: name, danger: action === 'stop' || /axis/i.test(g.name || '') })) return;
    }
    await _dhRun(`pve:${g.vmid}:${action}`, name, g.name || String(g.vmid),
        `/api/devicehub/proxmox/${encodeURIComponent(g.vmid)}/${action}`, { confirm: action !== 'start' });
}

// ---------- 資料 ----------

function _dhDeviceActions(id) {
    const c = DH.controls && DH.controls.ok ? (DH.controls.devices || []).find((x) => x.id === id) : null;
    return c ? c.actions || [] : [];
}

function _dhDeviceWake(id) {
    const c = DH.controls && DH.controls.ok ? (DH.controls.devices || []).find((x) => x.id === id) : null;
    return c ? c.wake : null;
}

function _dhGuestActions(vmid) {
    const g = DH.controls && DH.controls.ok ? (DH.controls.proxmox || []).find((x) => x.vmid === vmid) : null;
    return g ? g.actions : null;
}

function _dhServerDevice() {
    const devs = (DH.data && DH.data.devices) || [];
    return devs.find((d) => d.wdog) || devs.find((d) => d.id === 'esp-server') || null;
}

function _dhServerView() {
    const d = _dhServerDevice();
    if (!d) return { key: 'unknown', label: '狀態不明', note: '伺服器電源控制器（esp-server）還沒連上 DeviceHub。' };
    const w = d.wdog;
    if (d.status !== 'online' || !w) {
        return { key: 'unknown', label: '狀態不明', note: `電源控制器「${d.name}」離線（最後回報 ${_dhAgo(d.last_seen)}）。` };
    }
    const wd = w.enabled ? '看門狗已啟用' : '看門狗未啟用';
    if (w.host_alive) return { key: 'ok', label: '運作中', note: `由「${d.name}」監測 · ${wd}` };
    if (w.planned_off) return { key: 'off', label: '已關機', note: `計畫關機 · ${wd}` };
    return { key: 'bad', label: '沒有回應', note: `偵測不到 Proxmox 主機 · ${wd}` };
}

async function loadDeviceHub(force = false) {
    const home = document.getElementById('dh-home');
    const legacy = document.getElementById('smart-legacy');
    if (!home) return;
    if (!_dhIsAdmin()) {  // 後端也會擋 403；這裡只是不發請求
        home.hidden = true;
        if (legacy) legacy.hidden = false;
        return;
    }
    if (!_dhVisible() || (DH.loading && !force)) return;
    DH.loading = true;
    try {
        const res = await authFetch('/api/devicehub/summary');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.configured) {
            home.hidden = true;
            if (legacy) legacy.hidden = false;
            return;
        }
        if (data.error) {
            DH.data = { ...(DH.data || {}), error: data.error };
        } else {
            DH.data = data;
            if (data.control) {
                const c = await authFetch('/api/devicehub/controls');
                DH.controls = c.ok ? await c.json() : { ok: false, error: `http_${c.status}` };
            } else {
                DH.controls = { ok: false, error: 'control_not_configured' };
            }
        }
        home.hidden = false;
        if (legacy) legacy.hidden = true;
        _dhRender();
        _dhLoadPower();
    } catch (e) {
        // authFetch 已顯示網路錯誤
    } finally {
        DH.loading = false;
    }
}

// ---------- 畫面 ----------

function _dhRender() {
    const data = DH.data;
    if (!data || !document.getElementById('dh-home')) return;
    _dhRenderHeadline();
    _dhRenderServer();
    _dhRenderSummary();
    _dhRenderDevices();
    _dhRenderGuests();
    _dhRenderAlerts();
    _dhRenderDashboard();
    const link = document.getElementById('dh-open');
    if (link && /^https:\/\//.test(data.ui_url || '')) {  // 只接受 https 網址
        link.href = data.ui_url;
        link.hidden = false;
    }
}

function _dhRenderHeadline() {
    const data = DH.data;
    const h = document.getElementById('dh-headline');
    const sub = document.getElementById('dh-subline');
    const devs = data.devices || [];
    const sv = _dhServerView();
    const espOff = devs.filter((d) => d.type === 'esp32' && d.status !== 'online');
    let text = '家裡一切正常。', level = 'ok';
    if (data.error) { text = '讀不到 DeviceHub。'; level = 'warn'; }
    else if (sv.key === 'bad') { text = '伺服器沒有回應。'; level = 'bad'; }
    else if (espOff.length === 1) { text = `「${espOff[0].name}」離線了。`; level = 'bad'; }
    else if (espOff.length > 1) { text = `有 ${espOff.length} 個控制器離線。`; level = 'bad'; }
    else if (!devs.length) { text = '還沒有設備連上 DeviceHub。'; level = 'warn'; }
    h.textContent = text;
    h.dataset.level = level;

    const parts = ['DeviceHub'];
    if (data.error) parts.push(data.error);
    const online = devs.filter((d) => d.status === 'online').length;
    parts.push(`${online} / ${devs.length} 台設備在線`);
    if (data.generated_at) parts.push(`資料時間 ${_dhClock(data.generated_at)}`);
    if (DH.controls && !DH.controls.ok) parts.push(`僅顯示狀態：${_dhErrorText(DH.controls.error)}`);
    sub.textContent = parts.join(' · ');
}

function _dhStat(label, value, unit) {
    return _dhEl('div', { class: 'dh-stat' }, _dhEl('span', { text: label }),
        _dhEl('b', {}, value, unit ? _dhEl('small', { text: unit }) : null));
}

function _dhRenderServer() {
    const sv = _dhServerView();
    const d = _dhServerDevice();
    document.getElementById('dh-server-dot').dataset.s = sv.key === 'off' ? 'off' : sv.key;
    document.getElementById('dh-server-state').textContent = sv.label;
    document.getElementById('dh-server-note').textContent = sv.note;

    const stats = [];
    const t = (d && d.telemetry) || {};
    if (typeof t.temp_c === 'number') stats.push(_dhStat('機櫃溫度', t.temp_c.toFixed(1), '°C'));
    if (typeof t.hum === 'number') stats.push(_dhStat('濕度', String(Math.round(t.hum)), '%'));
    const pve = DH.data.proxmox || {};
    if (pve.enabled && !pve.error) {
        const guests = pve.guests || [];
        stats.push(_dhStat('虛擬機執行中', String(guests.filter((g) => g.status === 'running').length), ` / ${guests.length}`));
    }
    document.getElementById('dh-server-stats').replaceChildren(...stats);

    const box = document.getElementById('dh-server-actions');
    const acts = d ? _dhDeviceActions(d.id).map((a) => a.action) : [];
    const buttons = [];
    if (d && d.status === 'online') {
        const alive = sv.key === 'ok';
        if (acts.includes('pwrbtn.press')) {
            const label = alive ? '短按電源鍵（關機）' : '短按電源鍵（開機）';
            buttons.push(_dhEl('button', {
                type: 'button', class: 'dh-btn', text: label, disabled: DH.busy.has(`${d.id}:pwrbtn.press`),
                onclick: () => _dhCommand(d, 'pwrbtn.press', { label, warn: alive ? DH_POWER_WARN.pressOn : DH_POWER_WARN.pressOff }),
            }));
        }
        if (acts.includes('pwrbtn.hold')) {
            buttons.push(_dhEl('button', {
                type: 'button', class: 'dh-btn danger', text: '長按強制關機', disabled: DH.busy.has(`${d.id}:pwrbtn.hold`),
                onclick: () => _dhCommand(d, 'pwrbtn.hold', { warn: DH_POWER_WARN.hold }),
            }));
        }
    }
    box.replaceChildren(...buttons);
}

function _dhRenderSummary() {
    const devs = DH.data.devices || [];
    const pve = DH.data.proxmox || {};
    const guests = pve.enabled ? pve.guests || [] : [];
    const since = Date.now() / 1000 - 86400;
    const alerts = (DH.data.alerts || []).filter((a) => a.ts >= since && a.level !== 'notice');
    const tile = (id, a, b) => document.getElementById(id).replaceChildren(String(a), b != null ? _dhEl('small', { text: ` / ${b}` }) : '');
    tile('dh-sum-dev', devs.filter((d) => d.status === 'online').length, devs.length);
    tile('dh-sum-vm', guests.filter((g) => g.status === 'running').length, guests.length);
    tile('dh-sum-alert', alerts.length, null);
}

const _DH_STATUS = { online: ['在線', 'ok'], offline: ['離線', 'bad'], unknown: ['未知', 'unknown'] };

function _dhMetric(label, value, unit, pct) {
    return _dhEl('div', { class: 'dh-metric' }, _dhEl('span', { text: label }),
        _dhEl('b', { class: 'dh-num' }, value, unit ? _dhEl('small', { text: unit }) : null),
        typeof pct === 'number' ? _dhEl('div', { class: 'dh-bar' }, _dhEl('i', { style: `width:${Math.max(0, Math.min(100, pct))}%` })) : null);
}

function _dhDeviceCard(d) {
    const [label, s] = _DH_STATUS[d.status] || [d.status, 'unknown'];
    const t = d.telemetry || {};
    const server = _dhServerDevice();
    const kind = d.type === 'esp32' ? (server && server.id === d.id ? '伺服器電源控制器' : 'ESP32') : d.type === 'host' ? '電腦' : (d.type || '');
    const card = _dhEl('article', { class: 'dh-panel dh-card', 'data-status': d.status },
        _dhEl('div', { class: 'dh-card-head' },
            _dhEl('span', { class: 'dh-dot', 'data-s': s }),
            _dhEl('b', { class: 'dh-card-name', text: d.name }),
            _dhEl('span', { class: 'dh-card-id', text: d.id }),
            _dhEl('span', { class: 'dh-card-side', text: `${label} · ${kind}` })));

    const metrics = [];
    if (typeof t.temp_c === 'number') metrics.push(_dhMetric('溫度', t.temp_c.toFixed(1), '°C'));
    if (typeof t.hum === 'number') metrics.push(_dhMetric('濕度', String(Math.round(t.hum)), '%'));
    if (typeof t.cpu === 'number') metrics.push(_dhMetric('CPU', String(Math.round(t.cpu)), '%', t.cpu));
    if (typeof t.ram === 'number') metrics.push(_dhMetric('記憶體', String(Math.round(t.ram)), '%', t.ram));
    if (typeof t.disk === 'number') metrics.push(_dhMetric('磁碟', String(Math.round(t.disk)), '%', t.disk));
    if (typeof t.rssi === 'number') metrics.push(_dhMetric('WiFi', String(t.rssi), 'dBm'));
    if (metrics.length) card.append(_dhEl('div', { class: 'dh-metrics' }, ...metrics.slice(0, 6)));

    const facts = [`最後回報 ${_dhAgo(d.last_seen)}`];
    const up = _dhUptime(t.uptime);
    if (up && d.status === 'online') facts.push(`已運作 ${up}`);
    card.append(_dhEl('div', { class: 'dh-facts', text: facts.join(' · ') }));

    const acts = _dhDeviceActions(d.id).map((a) => a.action);
    const box = _dhEl('div', { class: 'dh-actions' });
    const btn = (action, { tone = '', label = null } = {}) => _dhEl('button', {
        type: 'button', class: `dh-btn small ${tone}`, text: label || DH_ACTION_LABELS[action],
        disabled: DH.busy.has(`${d.id}:${action}`), onclick: () => _dhCommand(d, action, { label }),
    });
    if (d.status === 'online') {
        if (d.type === 'host') {
            for (const a of ['host.sleep', 'host.restart']) if (acts.includes(a)) box.append(btn(a));
            if (acts.includes('host.shutdown')) box.append(btn('host.shutdown', { tone: 'danger' }));
        } else if (d.type === 'esp32') {
            if (acts.includes('sys.reboot')) box.append(btn('sys.reboot', { tone: 'danger', label: '重啟 ESP32' }));
        }
        if (acts.includes('ping')) box.append(btn('ping'));
    } else if (d.type === 'host') {
        const w = _dhDeviceWake(d.id);
        if (w && w.direct) {
            box.append(_dhEl('button', {
                type: 'button', class: 'dh-btn small primary', text: '喚醒', disabled: DH.busy.has(`${d.id}:wake`),
                onclick: () => _dhWake(d),
            }));
            for (const via of w.via || []) {
                box.append(_dhEl('button', {
                    type: 'button', class: 'dh-btn small', text: `經 ${via} 喚醒`, disabled: DH.busy.has(`${d.id}:wake`),
                    onclick: () => _dhWake(d, via),
                }));
            }
        }
    }
    if (box.children.length) card.append(box);
    return card;
}

function _dhRenderDevices() {
    const devs = [...(DH.data.devices || [])].sort((a, b) =>
        (a.type === b.type ? 0 : a.type === 'host' ? -1 : 1) || a.name.localeCompare(b.name, 'zh-Hant'));
    const box = document.getElementById('dh-devices');
    box.replaceChildren(...devs.map(_dhDeviceCard));
    if (!devs.length) box.append(_dhEl('p', { class: 'dh-muted', text: '還沒有設備連上 DeviceHub。' }));
}

const _DH_GUEST_STATUS = { running: '執行中', stopped: '已停止', paused: '已暫停', suspended: '已暫停' };

function _dhRenderGuests() {
    const pve = DH.data.proxmox || {};
    const sec = document.getElementById('dh-pve-sec');
    sec.hidden = !pve.enabled;
    if (!pve.enabled) return;
    document.getElementById('dh-pve-error').textContent = pve.error ? `讀不到 Proxmox：${pve.error}` : '';
    const rows = (pve.guests || []).map((g) => {
        const running = g.status === 'running';
        const acts = _dhGuestActions(g.vmid);
        const ops = _dhEl('div', { class: 'dh-vm-ops', role: 'cell' });
        if (acts === null && DH.controls && DH.controls.ok) {
            ops.append(_dhEl('span', { class: 'dh-muted', text: 'DeviceHub 所在，無法操作' }));
        }
        for (const a of acts || []) {
            ops.append(_dhEl('button', {
                type: 'button', class: `dh-btn small ${a === 'stop' ? 'danger' : a === 'start' ? 'primary' : ''}`,
                text: DH_ACTION_LABELS[`pve.${a}`], disabled: DH.busy.has(`pve:${g.vmid}:${a}`),
                onclick: () => _dhPower(g, a),
            }));
        }
        const mem = running && g.maxmem ? `${((g.mem || 0) / 1024 ** 3).toFixed(1)} / ${(g.maxmem / 1024 ** 3).toFixed(1)} GB` : '—';
        return _dhEl('div', { class: 'dh-vm-row', role: 'row', 'data-running': String(running) },
            _dhEl('div', { class: 'dh-vm-name', role: 'cell' }, _dhEl('b', { text: g.name || `#${g.vmid}` }),
                _dhEl('span', { text: `${g.type === 'lxc' ? 'CT' : 'VM'} ${g.vmid}` })),
            _dhEl('div', { class: 'dh-vm-status', role: 'cell' }, _dhEl('span', { class: 'dh-dot', 'data-s': running ? 'ok' : 'off' }),
                _dhEl('span', { text: _DH_GUEST_STATUS[g.status] || g.status || '—' })),
            _dhEl('div', { class: 'dh-num', role: 'cell', text: running ? `${Math.round((g.cpu || 0) * 100)} %` : '—' }),
            _dhEl('div', { class: 'dh-num', role: 'cell', text: mem }),
            ops);
    });
    document.getElementById('dh-guests').replaceChildren(...rows);
}

function _dhRenderAlerts() {
    const list = document.getElementById('dh-alerts');
    const alerts = DH.data.alerts || [];
    list.replaceChildren(...alerts.map((a) => _dhEl('li', { 'data-level': a.level },
        _dhEl('time', { text: _dhStamp(a.ts), title: new Date(a.ts * 1000).toLocaleString('zh-TW', { hour12: false }) }),
        _dhEl('span', { class: 'dh-msg', text: a.message }))));
    if (!alerts.length) list.append(_dhEl('li', { class: 'dh-calm', text: '目前沒有告警，一切安好。' }));
}

// ---------- 省電（DeviceHub FR-19；唯讀，30 秒更新一次） ----------

const _DH_POWER_ACTIONS = {
    'host.sleep': '睡眠', 'host.shutdown': '關機', 'host.wake': '開機（WOL）', 'pve.shutdown': '關機', 'pve.start': '開機',
};
const _DH_POWER_RESULTS = {
    ok: '成功', error: '失敗', expired: '逾時', unknown: '中斷', cancelled: '已取消',
    skipped_busy: '略過（使用中）', skipped_offline: '略過（本來就關著）', skipped_online: '略過（本來就開著）',
};
const _DH_DAYS = ['一', '二', '三', '四', '五', '六', '日'];

function _dhPowerDays(days) {
    if (!days) return '閒置時';
    if (days === '1234567') return '每天';
    if (days === '12345') return '週一～五';
    if (days === '67') return '週六、日';
    return '週' + [...days].map((d) => _DH_DAYS[Number(d) - 1] || '').join('、');
}

function _dhWhen(ts) {
    return new Date(ts * 1000).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
}

async function _dhLoadPower(force = false) {
    const now = Date.now();
    if (!force && DH.powerAt && now - DH.powerAt < 30000) return;
    DH.powerAt = now;
    try {
        const r = await authFetch('/api/devicehub/power');
        DH.power = r.ok ? await r.json() : null;
    } catch (e) {
        DH.power = null;
    }
    _dhRenderPower();
}

function _dhRenderPower() {
    const sec = document.getElementById('dh-power-sec');
    if (!sec) return;
    const p = DH.power;
    const ok = !!(p && p.ok);
    const rules = ok ? p.rules || [] : [];
    const saved = ok && p.savings ? p.savings : { targets: [], cpu_energy: [] };
    const mc = p && p.minecraft;
    sec.hidden = !(rules.length || saved.targets.length || saved.cpu_energy.length || mc);
    if (sec.hidden) return;

    const paused = ok && p.paused_until > Date.now() / 1000;
    const on = rules.filter((r) => r.enabled).length;
    document.getElementById('dh-power-status').textContent = !ok ? 'DeviceHub 的省電資料暫時讀不到。'
        : paused ? `省電自動化已暫停，${_dhWhen(p.paused_until)} 自動恢復。`
        : `省電自動化運作中・${on} / ${rules.length} 條規則啟用`;

    document.getElementById('dh-power-rules').replaceChildren(...rules.map((r) => {
        const meta = [];
        if (r.state === 'notice') meta.push('預告中');
        else if (r.state === 'waiting') meta.push('等待閒置');
        else if (r.state === 'sending') meta.push('執行中');   // 指令已送出、等結果（integration-api §3.1b）
        if (!r.enabled) meta.push('已停用');
        else if (r.next_run_at) meta.push(`下次 ${_dhWhen(r.next_run_at)}`);
        if (r.last_result) meta.push(`上次：${_DH_POWER_RESULTS[r.last_result] || r.last_result}`);
        return _dhEl('li', { 'data-enabled': String(!!r.enabled) },
            _dhEl('b', { text: r.name || '' }),
            _dhEl('span', { text: `${_dhPowerDays(r.days)}${r.time ? ` ${r.time}` : ''}・${r.target_name || ''} → ${_DH_POWER_ACTIONS[r.action] || r.action || ''}` }),
            _dhEl('span', { class: 'dh-muted', text: meta.join('・') }));
    }));

    const parts = [];
    for (const t of saved.targets) {
        let s = `${t.target_name} 省電 ${Number(t.off_h_total || 0).toFixed(0)} 小時`;
        if (t.est_kwh_saved != null) s += `（約 ${Number(t.est_kwh_saved).toFixed(1)} kWh）`;
        parts.push(s);
    }
    if (mc) parts.push(`Minecraft 暫停 ${(mc.week_paused_min / 60).toFixed(0)} 小時`);
    for (const c of saved.cpu_energy) parts.push(`${c.name} CPU 耗電 ${Number(c.kwh_total || 0).toFixed(1)} kWh`);
    document.getElementById('dh-power-saved').textContent = parts.length ? `最近 7 天：${parts.join('・')}` : '';
}

// ---------- 總覽頁的小工具（只給管理員）：快速控制、設備 ----------
// 圖示是固定的 SVG 字串（不含任何來自 DeviceHub 的資料），名稱一律用 textContent。

const _DH_SVG = {
    desktop: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M8 20h8M12 16v4"></path></svg>',
    laptop: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="10" rx="1.5"></rect><path d="M2 19h20"></path></svg>',
    chip: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5"></rect><path d="M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4"></path></svg>',
    power: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v8"></path><path d="M6.3 6.8a8 8 0 1 0 11.4 0"></path></svg>',
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"></path></svg>',
    server: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="7" rx="2"></rect><rect x="3.5" y="13" width="17" height="7" rx="2"></rect></svg>',
    home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 11l8.5-7 8.5 7"></path><path d="M6 10v10h12V10"></path></svg>',
};

function _dhDeviceSvg(d) {
    if (d.type === 'esp32') return _DH_SVG.chip;
    const text = `${d.id} ${d.name}`.toLowerCase();
    return /laptop|筆電|notebook/.test(text) ? _DH_SVG.laptop : _DH_SVG.desktop;
}

function _dhQuickButton(label, svg, tone, handler, busyKey) {
    const btn = _dhEl('button', { type: 'button', class: `quick-btn ${tone}`, onclick: handler,
        disabled: busyKey ? DH.busy.has(busyKey) : false });
    const ico = _dhEl('span', { class: 'q-ico' });
    ico.innerHTML = svg;
    btn.append(ico, _dhEl('span', { text: label }));
    return btn;
}

function _dhRenderDashboard() {
    const list = document.getElementById('dash-dev-list');
    const quick = document.getElementById('dash-quick-grid');
    if (!list || !quick || !DH.data || DH.data.error) return;
    const devs = [...(DH.data.devices || [])].sort((a, b) =>
        (a.type === b.type ? 0 : a.type === 'host' ? -1 : 1) || a.name.localeCompare(b.name, 'zh-Hant'));
    const server = _dhServerDevice();
    const online = devs.filter((d) => d.status === 'online').length;
    const title = document.getElementById('dash-dev-title');
    if (title) title.textContent = `設備 · ${online} / ${devs.length} 在線`;

    list.replaceChildren(...devs.map((d) => {
        const on = d.status === 'online';
        const t = d.telemetry || {};
        let sub = on ? '在線' : `離線 · ${_dhAgo(d.last_seen)}`;
        if (on && server && server.id === d.id) sub = '在線 · 電源控制器';
        else if (on && typeof t.cpu === 'number') sub = `在線 · CPU ${Math.round(t.cpu)}%`;
        const circle = _dhEl('span', { class: 'dr-circle' });
        circle.innerHTML = _dhDeviceSvg(d);
        return _dhEl('div', { class: 'dev-ring', 'data-on': String(on) }, circle,
            _dhEl('span', { class: 'dr-name', text: d.name }), _dhEl('span', { class: 'dr-sub', text: sub }));
    }));

    const btns = [];
    if (DH.controls && DH.controls.ok) {
        for (const d of devs.filter((x) => x.type === 'host').slice(0, 2)) {
            const acts = _dhDeviceActions(d.id).map((a) => a.action);
            if (d.status === 'online' && acts.includes('host.sleep')) {
                btns.push(_dhQuickButton(`${d.name} 睡眠`, _DH_SVG.moon, '', () => _dhCommand(d, 'host.sleep'), `${d.id}:host.sleep`));
            } else if (d.status !== 'online') {
                const w = _dhDeviceWake(d.id);
                if (w && w.direct) btns.push(_dhQuickButton(`喚醒 ${d.name}`, _DH_SVG.power, 'on', () => _dhWake(d), `${d.id}:wake`));
            }
        }
        if (server && server.status === 'online' && _dhDeviceActions(server.id).some((a) => a.action === 'pwrbtn.press')) {
            const alive = _dhServerView().key === 'ok';
            const label = alive ? '短按電源鍵（關機）' : '短按電源鍵（開機）';
            btns.push(_dhQuickButton('伺服器電源', _DH_SVG.server, 'danger',
                () => _dhCommand(server, 'pwrbtn.press', { label, warn: alive ? DH_POWER_WARN.pressOn : DH_POWER_WARN.pressOff }),
                `${server.id}:pwrbtn.press`));
        }
    }
    btns.push(_dhQuickButton('智慧宅控', _DH_SVG.home, '', () => switchView('smart'), null));
    quick.replaceChildren(...btns.slice(0, 4));
}

async function loadDeviceHubDashboard(force = false) {
    const quick = document.getElementById('dash-quick');
    const devices = document.getElementById('dash-devices');
    if (!quick || !devices) return;
    if (!_dhIsAdmin()) { quick.hidden = true; devices.hidden = true; return; }
    const view = document.querySelector('.view-section.active');
    if (!view || view.id !== 'view-dashboard' || (DH.loading && !force)) return;
    DH.loading = true;
    try {
        const res = await authFetch('/api/devicehub/summary');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.configured || data.error) { quick.hidden = true; devices.hidden = true; return; }
        DH.data = data;
        if (data.control) {
            const c = await authFetch('/api/devicehub/controls');
            DH.controls = c.ok ? await c.json() : { ok: false, error: `http_${c.status}` };
        } else {
            DH.controls = { ok: false, error: 'control_not_configured' };
        }
        quick.hidden = false;
        devices.hidden = false;
        _dhRenderDashboard();
    } catch (e) {
        // authFetch 已顯示網路錯誤
    } finally {
        DH.loading = false;
    }
}

document.addEventListener('view-switched', (e) => {
    if (e.detail && e.detail.view === 'dashboard') loadDeviceHubDashboard(true);
});
setInterval(loadDeviceHubDashboard, 10000);
