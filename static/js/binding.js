/**
 * Absolute Axis - 智慧宅控「綁定裝置」（DeviceHub integration-api.md §3.8、requirements FR-18）
 * 列出 DeviceHub 上的裝置帳號、新增（建立帳號後只顯示一次密碼與設定步驟）、移除。
 * - 只給管理員；後端 /api/devicehub/accounts* 會再檢查一次。
 * - 裝置名稱等文字一律 textContent；showToast() 會插入 HTML，所以傳進去前先跳脫。
 * - 密碼只存在對話框裡，關閉（含按 Esc）就清掉，不寫進 localStorage、不記錄。
 */

const BIND = { kind: 'esp32', accounts: [], busy: false };
const BIND_ID_RE = /^[a-z][a-z0-9-]{1,30}$/;
const BIND_PROTECTED = new Set(['esp-server']);  // 伺服器電源控制器（看門狗設備），DeviceHub 也會拒絕移除

const BIND_KINDS = {
    esp32: { label: 'ESP32 節點', color: '#F2992E', placeholder: '例如 esp-living',
             paths: ['M7 7h10v10H7z', 'M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4'] },
    windows: { label: 'Windows 電腦', color: '#3E7BFA', placeholder: '例如 office-pc',
               paths: ['M3.5 5h17v11h-17z', 'M9 20h6M12 16v4'] },
    linux: { label: 'Linux 電腦', color: '#4A4A54', placeholder: '例如 nas-box',
             paths: ['M3.5 5h17v14h-17z', 'M7 10l3 2.5L7 15M12 15h5'] },
};

const BIND_ERRORS = {
    exists: '這個代號已經被使用了，請換一個。',
    reserved: '這是系統保留的代號，請換一個。',
    bad_id: '代號格式不對：小寫英文、數字與「-」，2–31 字、英文開頭。',
    bad_request: '代號或類型格式不對。',
    bad_name: '名稱要 1–40 個字。',
    protected: '伺服器電源控制器不能移除。',
    unknown_account: '找不到這個裝置，可能已經被移除了。',
    control_not_configured: 'Axis 尚未設定 DeviceHub 控制權杖（DEVICEHUB_CONTROL_TOKEN）。',
    not_configured: 'DeviceHub 還沒安裝裝置帳號工具（CT 150 需重新部署）。',
    unreachable: '連不到 DeviceHub，請稍後再試。',
    rate_limited: '操作太頻繁，請 10 分鐘後再試。',
    unauthorized: 'DeviceHub 拒絕了 Axis 的權杖。',
    forbidden: 'DeviceHub 拒絕了這台主機的來源位址。',
};

function _bindError(code) {
    return BIND_ERRORS[code] || `操作失敗（${code || '未知錯誤'}）`;
}

function _bindEsc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function _bindToast(msg, type = 'info') {
    if (typeof showToast === 'function') showToast(_bindEsc(msg), type);
}

function _bindIcon(kind) {
    const k = BIND_KINDS[kind] || BIND_KINDS.linux;
    const box = document.createElement('span');
    box.className = 'nav-ico';
    box.style.background = k.color;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    for (const d of k.paths) {
        const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', d);
        svg.append(p);
    }
    box.append(svg);
    return box;
}

function _bindIsAdmin() {
    const role = localStorage.getItem('axis_role');
    return role === 'Administrator' || role === 'admin';
}

// ---------- 清單 ----------

async function loadDeviceBinding() {
    const msg = document.getElementById('bind-msg');
    const add = document.getElementById('bind-add');
    const list = document.getElementById('bind-list');
    if (!msg || !list) return;
    if (!_bindIsAdmin()) {
        msg.textContent = '只有管理員可以管理裝置。';
        msg.hidden = false;
        add.hidden = true;
        list.hidden = true;
        return;
    }
    add.hidden = false;
    list.hidden = false;
    try {
        const r = await authFetch('/api/devicehub/accounts');
        const data = r.ok ? await r.json() : { ok: false, error: `http_${r.status}` };
        if (!data.ok) {
            msg.textContent = _bindError(data.error);
            msg.hidden = false;
            add.disabled = ['control_not_configured', 'not_configured'].includes(data.error);
            list.replaceChildren();
            return;
        }
        msg.hidden = true;
        add.disabled = false;
        BIND.accounts = Array.isArray(data.accounts) ? data.accounts : [];
        _bindRender();
    } catch (e) {
        msg.textContent = _bindError('unreachable');
        msg.hidden = false;
    }
}

function _bindState(a) {
    if (a.status === 'online') return ['online', '在線'];
    if (!a.connected) return ['pending', '尚未連線'];
    return ['offline', '離線'];
}

function _bindRender() {
    const list = document.getElementById('bind-list');
    const rows = BIND.accounts.slice().sort((x, y) =>
        String(x.name || x.id).localeCompare(String(y.name || y.id), 'zh-Hant'));
    if (!rows.length) {
        const empty = document.createElement('div');
        empty.className = 'ios-row static';
        const t = document.createElement('span');
        t.className = 'ios-label ios-muted';
        t.textContent = '還沒有綁定任何裝置。按「新增裝置」開始。';
        empty.append(t);
        list.replaceChildren(empty);
        return;
    }
    list.replaceChildren(...rows.map((a) => {
        const row = document.createElement('div');
        row.className = 'ios-row static bind-row';
        const kind = a.type === 'esp32' ? 'esp32' : a.type === 'host' ? 'windows' : 'linux';

        const main = document.createElement('span');
        main.className = 'bind-main';
        const name = document.createElement('b');
        name.textContent = a.name || a.id;
        const sub = document.createElement('span');
        sub.textContent = `${a.id} · ${a.type === 'esp32' ? 'ESP32' : a.type === 'host' ? '電腦' : '尚未回報類型'}`;
        main.append(name, sub);

        const [s, label] = _bindState(a);
        const state = document.createElement('span');
        state.className = 'bind-state';
        state.dataset.s = s;
        state.append(document.createElement('i'), label);

        row.append(_bindIcon(kind), main, state);
        if (BIND_PROTECTED.has(a.id)) {
            const note = document.createElement('span');
            note.className = 'bind-note';
            note.textContent = '伺服器電源控制器';
            row.append(note);
        } else {
            const rm = document.createElement('button');
            rm.type = 'button';
            rm.className = 'btn btn-danger bind-remove';
            rm.textContent = '移除';
            rm.addEventListener('click', () => _bindRemove(a));
            row.append(rm);
        }
        return row;
    }));
}

async function _bindRemove(a) {
    const name = a.name || a.id;
    const ok = typeof _dhAsk === 'function'
        ? await _dhAsk(`移除「${name}」？`,
            '會刪除它的連線帳號並清除狀態與歷史紀錄；裝置會立刻斷線。之後要再加回來，必須重新新增並重新設定裝置。',
            { ok: '移除', danger: true })
        : false;
    if (!ok) return;
    try {
        const r = await authFetch(`/api/devicehub/accounts/${encodeURIComponent(a.id)}`, {
            method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: true }),
        });
        const data = await r.json();
        if (data.ok) _bindToast(`已移除「${name}」`, 'success');
        else _bindToast(_bindError(data.error), 'error');
    } catch (e) {
        _bindToast(_bindError('unreachable'), 'error');
    }
    loadDeviceBinding();
}

// ---------- 新增 ----------

function _bindSetKind(kind) {
    BIND.kind = kind;
    document.querySelectorAll('#bind-kind button').forEach((b) =>
        b.setAttribute('aria-pressed', String(b.dataset.kind === kind)));
    const id = document.getElementById('bind-id');
    if (id) id.placeholder = BIND_KINDS[kind].placeholder;
}

window.openBindAdd = function () {
    const dlg = document.getElementById('bind-dialog');
    if (!dlg || typeof dlg.showModal !== 'function') return;
    _bindClearResult();
    document.getElementById('bind-form').hidden = false;
    document.getElementById('bind-result').hidden = true;
    document.getElementById('bind-id').value = '';
    document.getElementById('bind-name').value = '';
    document.getElementById('bind-error').textContent = '';
    document.getElementById('bind-submit').disabled = false;
    _bindSetKind('esp32');
    dlg.showModal();
    document.getElementById('bind-id').focus();
};

window.closeBindDialog = function () {
    const dlg = document.getElementById('bind-dialog');
    _bindClearResult();
    if (dlg && dlg.open) dlg.close();
};

function _bindClearResult() {
    for (const id of ['bind-r-id', 'bind-r-pw']) {
        const el = document.getElementById(id);
        if (el) el.value = '';
    }
    const snip = document.getElementById('bind-r-snippet');
    if (snip) snip.textContent = '';
}

window.submitBindAdd = async function () {
    if (BIND.busy) return;
    const id = document.getElementById('bind-id').value.trim();
    const name = document.getElementById('bind-name').value.trim();
    const err = document.getElementById('bind-error');
    if (!BIND_ID_RE.test(id)) {
        err.textContent = _bindError('bad_id');
        return;
    }
    err.textContent = '';
    BIND.busy = true;
    const btn = document.getElementById('bind-submit');
    btn.disabled = true;
    try {
        const r = await authFetch('/api/devicehub/accounts', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, name: name || null, kind: BIND.kind }),
        });
        const data = await r.json();
        if (!data.ok) {
            err.textContent = _bindError(data.error);
            return;
        }
        _bindShowResult(data);
        loadDeviceBinding();
    } catch (e) {
        err.textContent = _bindError('unreachable');
    } finally {
        BIND.busy = false;
        btn.disabled = false;
    }
};

function _bindShowResult(data) {
    const guide = _bindGuide(data.kind, data.id, data.password, data.mqtt || {});
    document.getElementById('bind-r-name').textContent = data.name || data.id;
    document.getElementById('bind-r-id').value = data.id;
    document.getElementById('bind-r-pw').value = data.password;
    document.getElementById('bind-r-file').textContent = guide.file;
    document.getElementById('bind-r-snippet').textContent = guide.text;
    const steps = document.getElementById('bind-r-steps');
    steps.replaceChildren(...guide.steps.map((parts) => {
        const li = document.createElement('li');
        for (const p of parts) {
            if (typeof p === 'string') {
                li.append(p);
            } else {
                const code = document.createElement('code');
                code.textContent = p.code;
                li.append(code);
            }
        }
        return li;
    }));
    document.getElementById('bind-form').hidden = true;
    document.getElementById('bind-result').hidden = false;
}

// 每種裝置的設定內容與步驟（DeviceHub repo：firmware/README.md、agent/README.md）
function _bindGuide(kind, id, pw, mqtt) {
    const lan = mqtt.lan || '<DeviceHub 主機 IP>';
    const port = mqtt.port || 1883;
    if (kind === 'esp32') {
        return {
            file: '韌體設定：DeviceHub 專案的 firmware/include/secrets.h',
            text: [
                '#pragma once',
                '#define DH_WIFI_SSID "你的 WiFi 名稱"      // ESP32 只支援 2.4 GHz',
                '#define DH_WIFI_PASS "你的 WiFi 密碼"',
                `#define DH_MQTT_HOST "${lan}"`,
                `#define DH_MQTT_PORT ${port}`,
                `#define DH_DEVICE_ID "${id}"`,
                `#define DH_MQTT_PASS "${pw}"`,
                '#define DH_OTA_PASS "自訂一組無線更新密碼"',
            ].join('\n'),
            steps: [
                ['在 DeviceHub 專案的 ', { code: 'firmware/include/' }, ' 建立 ', { code: 'secrets.h' }, '，貼上上面的設定，填入 WiFi 名稱、WiFi 密碼與無線更新密碼。'],
                ['用 USB 把 ESP32 接到電腦，在 ', { code: 'firmware' }, ' 資料夾執行 ', { code: 'pio run -e node -t upload' }, '。'],
                ['燒好後約 1 分鐘，這裡會從「尚未連線」變成「在線」。也可以把這個畫面交給桌機的 Claude 代為燒錄。'],
            ],
        };
    }
    const host = mqtt.tailnet || lan;
    const hostNote = mqtt.tailnet
        ? `# Tailscale 位址：外出也能連（這台電腦要裝 Tailscale）；只在家用可改成 "${lan}"`
        : '# 家中區網位址';
    const toml = [
        `device_id = "${id}"`,
        '',
        '[mqtt]',
        hostNote,
        `host = "${host}"`,
        `port = ${port}`,
        `password = "${pw}"`,
    ].join('\n');
    if (kind === 'windows') {
        return {
            file: '電腦設定：C:\\ProgramData\\DeviceHub\\agent.toml',
            text: toml,
            steps: [
                ['在這台電腦取得 DeviceHub 專案（', { code: 'git clone https://github.com/deven951130/DeviceHub' }, '）。'],
                ['以系統管理員開啟 PowerShell，在專案資料夾執行 ', { code: 'powershell -ExecutionPolicy Bypass -File agent\\install-windows.ps1' }, '。'],
                ['用記事本打開 ', { code: 'C:\\ProgramData\\DeviceHub\\agent.toml' }, '，整個換成上面的內容並存檔。'],
                ['執行 ', { code: 'Start-ScheduledTask -TaskName "DeviceHub Agent"' }, '；約 30 秒後這裡會顯示「在線」。'],
            ],
        };
    }
    return {
        file: '電腦設定：/etc/devicehub/agent.toml',
        text: toml,
        steps: [
            ['取得 DeviceHub 專案後執行 ', { code: 'python3 -m venv /opt/devicehub/agent-venv && /opt/devicehub/agent-venv/bin/pip install ./agent' }, '。'],
            ['把上面的內容存成 ', { code: '/etc/devicehub/agent.toml' }, '，並執行 ', { code: 'chmod 600 /etc/devicehub/agent.toml' }, '。'],
            ['複製 ', { code: 'agent/devicehub-agent.service' }, ' 到 ', { code: '/etc/systemd/system/' }, '，執行 ', { code: 'systemctl enable --now devicehub-agent' }, '。'],
        ],
    };
}

window.copyBindSnippet = async function () {
    const text = document.getElementById('bind-r-snippet').textContent;
    try {
        await navigator.clipboard.writeText(text);
        _bindToast('設定已複製', 'success');
    } catch (e) {
        // 沒有剪貼簿權限（例如區網 http）：選取文字讓使用者自己按複製
        const range = document.createRange();
        range.selectNodeContents(document.getElementById('bind-r-snippet'));
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        _bindToast('已選取設定，請按 Ctrl+C（手機長按）複製', 'info');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // 頁面元件是 app.js 動態載入的：等 view-switched 之後才綁定
    document.addEventListener('click', (e) => {
        const b = e.target.closest && e.target.closest('#bind-kind button');
        if (b) _bindSetKind(b.dataset.kind);
    });
    document.addEventListener('close', (e) => {
        if (e.target && e.target.id === 'bind-dialog') _bindClearResult();  // 含按 Esc 關閉
    }, true);
});
