/**
 * Absolute Axis - Multiverse Module
 * Handles Minecraft server status polling and admin command injection.
 */

// 自動刷新 Timer handle
let _mvRefreshTimer = null;

/**
 * 載入並渲染 Multiverse 頁面資料。
 * 由 ui.js switchView('multiverse') 觸發，以及定時自動刷新。
 */
async function loadMultiverse() {
    try {
        const res = await authFetch('/api/minecraft/status');
        if (!res.ok) {
            _mvRenderError(`API 回應錯誤：HTTP ${res.status}`);
            return;
        }
        const data = await res.json();
        _mvRenderStatus(data);
        
        // 載入模組包簡介與管理資訊
        await loadMultiverseInfo();
    } catch (e) {
        _mvRenderError(`連線失敗：${e.message}`);
    }
}

async function loadMultiverseInfo() {
    try {
        const res = await authFetch('/api/minecraft/info');
        if (res.ok) {
            const info = await res.json();
            
            // 渲染簡介
            const display = document.getElementById('mv-desc-display');
            if (display) display.textContent = info.description || '暫無說明。';
            
            const textarea = document.getElementById('mv-desc-textarea');
            if (textarea) textarea.value = info.description || '';
            
            // 渲染模組包名稱
            _mvSet('mv-server-pack-name', info.server_pack_name || '無');
            _mvSet('mv-client-pack-name', info.client_pack_name || '無');
            
            // 下載按鈕狀態
            const dlBtn = document.getElementById('mv-download-client-btn');
            if (dlBtn) {
                if (info.has_client_pack) {
                    dlBtn.disabled = false;
                    dlBtn.textContent = '下載客戶端模組包';
                } else {
                    dlBtn.disabled = true;
                    dlBtn.textContent = '尚未上傳客戶端模組包';
                }
            }
            
            // 管理端按鈕權限顯示
            const role = localStorage.getItem('axis_role');
            const isAdmin = (role === 'admin' || role === 'Administrator');
            const editDescBtn = document.getElementById('mv-edit-desc-btn');
            const adminControls = document.getElementById('mv-admin-pack-controls');
            const librarySection = document.getElementById('mv-pack-library-section');

            if (editDescBtn) editDescBtn.style.display = isAdmin ? '' : 'none';
            if (adminControls) adminControls.style.display = isAdmin ? 'flex' : 'none';
            if (librarySection) librarySection.style.display = isAdmin ? 'block' : 'none';
            if (isAdmin) loadPackLibrary();
        }
    } catch (e) {
        console.error("載入模組包資訊失敗:", e);
    }
}

/**
 * 渲染伺服器狀態至各 DOM 元素。
 */
// 分鐘數 → 「3 小時 20 分」
function _mvDuration(min) {
    const m = Math.max(0, Math.round(Number(min) || 0));
    const h = Math.floor(m / 60);
    return h ? `${h} 小時 ${m % 60} 分` : `${m} 分`;
}

function _mvRenderStatus(data) {
    const online = data.online;
    // 省電（autopause）：沒人玩一段時間後暫停，有人連線就醒來（DeviceHub FR-19c）
    const power = data.power || {};
    const paused = power.state === 'paused';
    const saved = power.week ? `本週省電 ${_mvDuration(power.week.paused_min)}（今天 ${_mvDuration(power.today.paused_min)}）` : '';

    // --- 頂部橫幅 ---
    const dot = document.getElementById('mv-banner-dot');
    const title = document.getElementById('mv-banner-title');
    const sub = document.getElementById('mv-banner-sub');
    const banner = document.getElementById('mv-status-banner');

    if (paused) {
        dot.style.background = 'var(--accent-color)';
        dot.style.boxShadow = '0 0 8px color-mix(in srgb, var(--accent-color) 60%, transparent)';
        title.textContent = 'Minecraft 伺服器省電中';
        sub.textContent = `沒有玩家，已自動暫停；有人連線就會醒來。${saved}`;
    } else if (online) {
        dot.style.background = 'var(--success-color)';
        dot.style.boxShadow = '0 0 8px color-mix(in srgb, var(--success-color) 70%, transparent)';
        title.textContent = 'Minecraft 伺服器運作中';
        sub.textContent = power.autopause
            ? `連線正常；沒人玩一段時間會自動省電。${saved}`
            : '連線正常，Java 版伺服器執行中';
    } else {
        dot.style.background = 'var(--danger-color)';
        dot.style.boxShadow = '0 0 8px color-mix(in srgb, var(--danger-color) 70%, transparent)';
        title.textContent = 'Minecraft 伺服器離線';
        sub.textContent = '連不上伺服器：服務可能已停止，或正在啟動中';
    }

    // 更新時間
    const el = document.getElementById('mv-last-update');
    if (el) el.textContent = new Date().toLocaleTimeString('zh-TW');

    // --- 伺服器資訊卡 ---
    _mvSet('mv-name', data.server?.name || '--');
    _mvSet('mv-version', data.server?.version || '--');
    _mvSet('mv-java', data.server?.java_version || '偵測失敗');
    _mvSet('mv-screen', data.server?.screen_session || '--');
    _mvSet('mv-uptime', data.server?.uptime || '--');

    // --- 連線資訊 ---
    _mvSet('mv-lan', data.connection?.address_lan || '--');
    const wanEl = document.getElementById('mv-wan');
    if (wanEl) {
        wanEl.textContent = data.connection?.address_wan || '--';
        wanEl.setAttribute('data-copy', data.connection?.address_wan_real || '');
    }
    _mvSet('mv-ddns', data.connection?.address_ddns || '--');

    // --- 硬體規格 ---
    _mvSet('mv-ram', data.specs?.ram || '--');
    _mvSet('mv-jvm', data.specs?.jvm_heap || '--');
    _mvSet('mv-cpu', `${data.specs?.cpu_threads || '--'} 執行緒`);
    _mvSet('mv-container', data.specs?.container || '--');

    // --- 脈搏狀態環 ---
    const ring = document.getElementById('mv-pulse-ring');
    const ringLabel = document.getElementById('mv-pulse-label');
    if (paused) {
        ring.style.border = '3px solid var(--accent-color)';
        ring.style.boxShadow = 'none';
        ring.style.animation = 'none';
        ringLabel.textContent = '省電中';
        ringLabel.style.color = 'var(--accent-color)';
    } else if (online) {
        ring.style.border = '3px solid var(--success-color)';
        ring.style.boxShadow = '0 0 12px color-mix(in srgb, var(--success-color) 50%, transparent)';
        ring.style.animation = 'mv-pulse-anim 2s infinite';
        ringLabel.textContent = '線上';
        ringLabel.style.color = 'var(--success-color)';
    } else {
        ring.style.border = '3px solid var(--danger-color)';
        ring.style.boxShadow = 'none';
        ring.style.animation = 'none';
        ringLabel.textContent = '離線';
        ringLabel.style.color = 'var(--danger-color)';
    }

    // --- 管理員限定面板顯示控制 ---
    const role = localStorage.getItem('axis_role');
    const isAdmin = (role === 'admin' || role === 'Administrator');
    const consoleSection = document.getElementById('mv-console-section');
    const quickPanel = document.getElementById('mv-quick-panel');
    if (consoleSection) consoleSection.style.display = isAdmin ? 'block' : 'none';
    if (quickPanel) quickPanel.style.display = isAdmin ? 'block' : 'none';
}

function _mvRenderError(msg) {
    const sub = document.getElementById('mv-banner-sub');
    if (sub) sub.textContent = msg;
    const el = document.getElementById('mv-last-update');
    if (el) el.textContent = new Date().toLocaleTimeString('zh-TW');
}

function _mvSet(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

/**
 * 複製指定元素的文字內容至剪貼簿。
 */
window.mvCopy = function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const textToCopy = el.getAttribute('data-copy') || el.textContent;
    navigator.clipboard.writeText(textToCopy).then(() => {
        const orig = el.style.color;
        el.style.color = 'var(--success-color)';
        setTimeout(() => { el.style.color = orig; }, 800);
    });
};

/**
 * 快速指令：填入預設指令至輸入框並送出。
 */
window.mvQuickCmd = function(cmd) {
    const input = document.getElementById('mv-cmd-input');
    if (input) {
        input.value = cmd;
        sendMCCommand();
    }
};

/**
 * 送出 MC 指令至後端 API。
 */
window.sendMCCommand = async function() {
    const input = document.getElementById('mv-cmd-input');
    const log = document.getElementById('mv-cmd-log');
    if (!input || !log) return;

    const command = input.value.trim();
    if (!command) return;

    // 立即在 log 顯示送出記錄（指令與錯誤訊息都用 textContent）
    const ts = new Date().toLocaleTimeString('zh-TW', { hour12: false });
    const pendingLine = _mvLogLine(ts, 'pending', command, '送出中…');
    log.appendChild(pendingLine);
    log.scrollTop = log.scrollHeight;
    input.value = '';

    try {
        const res = await authFetch('/api/minecraft/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await res.json().catch(() => ({}));
        pendingLine.replaceWith(res.ok
            ? _mvLogLine(ts, 'ok', command, typeof data.response === 'string' ? data.response : '')
            : _mvLogLine(ts, 'bad', command, typeof data.detail === 'string' ? data.detail : '未知錯誤'));
    } catch (e) {
        pendingLine.replaceWith(_mvLogLine(ts, 'bad', command, '網路錯誤'));
    }
    log.scrollTop = log.scrollHeight;
};

function _mvLogLine(ts, state, command, note) {
    const mark = { pending: '›', ok: '✓', bad: '✗' }[state];
    return h('div', { class: `mv-log-line ${state}` },
        h('span', { class: 'mv-log-ts', text: `[${ts}]` }),
        h('span', { class: 'mv-log-mark', text: mark }),
        h('span', { class: 'mv-log-cmd', text: command }),
        note ? h('span', { class: 'mv-log-note', text: `— ${note}` }) : null);
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 注入 CSS 動畫（僅注入一次）
if (!document.getElementById('mv-style')) {
    const style = document.createElement('style');
    style.id = 'mv-style';
    style.textContent = `
        @keyframes mv-pulse-anim {
            0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--success-color) 40%, transparent); }
            70% { box-shadow: 0 0 0 10px rgba(76,175,80,0); }
            100% { box-shadow: 0 0 0 0 rgba(76,175,80,0); }
        }
    `;
    document.head.appendChild(style);
}

window.toggleEditDesc = function(show) {
    const display = document.getElementById('mv-desc-display');
    const editArea = document.getElementById('mv-desc-edit-area');
    const editBtn = document.getElementById('mv-edit-desc-btn');
    const textarea = document.getElementById('mv-desc-textarea');
    
    if (show) {
        if (display) display.style.display = 'none';
        if (editArea) editArea.style.display = 'flex';
        if (editBtn) editBtn.style.display = 'none';
        if (textarea) textarea.focus();
    } else {
        if (display) display.style.display = '';
        if (editArea) editArea.style.display = 'none';
        if (editBtn) editBtn.style.display = '';
    }
};

window.saveDesc = async function() {
    const textarea = document.getElementById('mv-desc-textarea');
    if (!textarea) return;
    
    const description = textarea.value;
    try {
        const res = await authFetch('/api/minecraft/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });
        if (res.ok) {
            toastText("模組包說明已保存", "success");
            toggleEditDesc(false);
            await loadMultiverseInfo();
        } else {
            const data = await res.json();
            toastText(data.detail || "保存失敗", "error");
        }
    } catch (e) {
        toastText("網路錯誤：" + e.message, "error");
    }
};

// 名稱不能叫 triggerUpload：私有雲（nas.js）也用這個全域名稱，multiverse.js 較晚載入會把它蓋掉，
// 結果私有雲的「上傳檔案」變成打開模組包上傳（只收 .zip，且會存成公開的 static/minecraft-client-pack.zip）
window.mvTriggerUpload = function(type) {
    window._mvUploadType = type;
    const fileInput = document.getElementById('mv-file-input');
    if (fileInput) {
        fileInput.value = ''; // Reset
        fileInput.click();
    }
};

// ==================== 模組包函式庫 ====================

/**
 * 載入函式庫列表並渲染至 #mv-pack-list
 */
async function loadPackLibrary() {
    const container = document.getElementById('mv-pack-list');
    if (!container) return;
    const note = (text, tone = 'ios-muted') => container.replaceChildren(
        h('div', { class: 'ios-row static' }, h('span', { class: `ios-label ${tone}`, text })));
    note('載入中…');
    try {
        const res = await authFetch('/api/minecraft/packs');
        if (!res.ok) {
            note('函式庫載入失敗', 'mv-bad');
            return;
        }
        const data = await res.json();
        renderPackList(data.packs || []);
    } catch (e) {
        note('函式庫載入失敗：連線錯誤', 'mv-bad');
    }
}

/**
 * 渲染模組包清單（名稱來自上傳的檔名：一律 textContent＋事件綁定）
 */
function renderPackList(packs) {
    const container = document.getElementById('mv-pack-list');
    if (!container) return;
    if (!packs.length) {
        container.replaceChildren(h('div', { class: 'ios-row static' },
            h('span', { class: 'ios-label ios-muted', text: '函式庫是空的，請先上傳模組包。' })));
        return;
    }
    container.replaceChildren(...packs.map((pack) => {
        const inLibrary = pack.in_library !== false;
        const pills = [];
        if (pack.active) pills.push(h('span', { class: `pill ${inLibrary ? 'ok' : 'warn'}`, text: inLibrary ? '使用中' : '使用中・未存入庫' }));
        if (inLibrary) pills.push(h('span', { class: `pill ${pack.has_world ? 'info' : ''}`, text: pack.has_world ? '有世界存檔' : '全新地圖' }));
        const size = pack.size_mb != null ? `${pack.size_mb} MB` : '檔案不在函式庫中（需重新上傳才能存入）';
        const actions = h('span', { class: 'row-actions' });
        if (!pack.active) {
            actions.append(
                h('button', { type: 'button', class: 'btn btn-primary btn-sm', text: '切換部署',
                              onclick: () => window.switchPack(pack.name, !!pack.has_world) }),
                h('button', { type: 'button', class: 'btn btn-danger btn-sm', text: '刪除',
                              onclick: () => window.deletePackFromLibrary(pack.name) }));
        }
        return h('div', { class: 'ios-row static user-row' },
            h('span', { class: 'nav-ico', style: 'background:#20A6A6' }, _mvBoxIcon()),
            h('span', { class: 'row-main' },
                h('b', { text: pack.name }),
                h('span', { class: pack.size_mb != null ? '' : 'mv-warn', text: size })),
            pills,
            actions);
    }));
}

function _mvBoxIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    for (const d of ['M12 3l8 4.5v9L12 21l-8-4.5v-9z', 'M12 12l8-4.5M12 12v9M12 12L4 7.5']) {
        const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        p.setAttribute('d', d);
        svg.append(p);
    }
    return svg;
}



/**
 * 切換並部署指定模組包
 */
window.switchPack = async function(packName, hasWorld = false) {
    // 第一步：確認切換
    if (!(await axisAsk({
        title: `切換到「${packName}」？`,
        message: `會自動：\n・保存目前的世界存檔\n・${hasWorld ? '還原這個模組包的世界存檔' : '建立全新世界（這個包還沒有存檔）'}\n・重新啟動伺服器`,
        ok: '切換部署',
    }))) return;

    // 第二步：若該包已有存檔，詢問是否重置地圖
    let resetWorld = false;
    if (hasWorld) {
        // 按 Esc 或「沿用」＝保留舊地圖（安全的預設）
        resetWorld = await axisAsk({
            title: `「${packName}」有舊的世界存檔`,
            message: '要沿用這個存檔，還是刪掉它、產生全新地圖？刪除後無法復原。',
            ok: '刪除舊存檔、產生新地圖', cancel: '沿用舊地圖（建議）', danger: true,
        });
    }

    const progressLabel = resetWorld
        ? `正在切換至 ${packName}（重置地圖），停止伺服器中...`
        : `正在切換至 ${packName}，儲存目前地圖中...`;
    _mvShowProgress(0, progressLabel);

    try {
        const token = localStorage.getItem('axis_token');
        const res = await fetch('/api/minecraft/switch-pack', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ pack_name: packName, reset_world: resetWorld })
        });
        _mvHideProgress();
        const data = await res.json();
        if (res.ok) {
            const worldMsg = resetWorld
                ? '，已重置為全新地圖'
                : (hasWorld ? '，已還原該包的世界存檔' : '，全新地圖將在首次連線時生成');
            toastText(`已切換至 ${packName}${worldMsg}。Minecraft 模組載入需要數分鐘，請稍後再連線。`, 'success'
            );
            await loadMultiverse();
        } else {
            toastText(data.detail || '切換失敗', 'error');
        }
    } catch (e) {
        _mvHideProgress();
        toastText('切換錯誤：' + e.message, 'error');
    }
};


/**
 * 從函式庫刪除指定模組包
 */
window.deletePackFromLibrary = async function(packName) {
    if (!(await axisAsk({ title: `從函式庫刪除「${packName}」？`, message: '刪除後無法復原。', ok: '刪除', danger: true }))) return;

    try {
        const res = await authFetch(`/api/minecraft/packs/${encodeURIComponent(packName)}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            toastText(`已刪除 ${packName}`, 'success');
            await loadPackLibrary();
        } else {
            toastText(data.detail || '刪除失敗', 'error');
        }
    } catch (e) {
        toastText('刪除錯誤：' + e.message, 'error');
    }
};

// ==================== Upload Trigger ====================


window.handleFileSelected = function(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const type = window._mvUploadType;

    if (!file.name.endsWith('.zip')) {
        toastText("僅接受 .zip 壓縮包！", "warning");
        return;
    }

    const url = type === 'server' ? '/api/minecraft/upload-server' : '/api/minecraft/upload-client';
    const desc = type === 'server' ? '伺服器端包' : '客戶端包';

    // 顯示進度條 UI
    _mvShowProgress(0, `準備上傳 ${desc}（${(file.size / 1024 / 1024).toFixed(1)} MB）`);

    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem('axis_token');
    const xhr = new XMLHttpRequest();

    // 上傳進度回調
    let startTime = Date.now();
    xhr.upload.addEventListener('progress', function(e) {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        const elapsed = (Date.now() - startTime) / 1000;
        const speedMBps = (e.loaded / 1024 / 1024 / elapsed).toFixed(1);
        const remainBytes = e.total - e.loaded;
        const remainSec = Math.round(remainBytes / 1024 / 1024 / speedMBps);
        const remainStr = remainSec > 60
            ? `${Math.floor(remainSec / 60)} 分 ${remainSec % 60} 秒`
            : `${remainSec} 秒`;
        _mvShowProgress(pct, `上傳中 ${pct}%・速度 ${speedMBps} MB/s・剩餘約 ${remainStr}`);
    });

    xhr.addEventListener('load', async function() {
        _mvHideProgress();
        if (xhr.status >= 200 && xhr.status < 300) {
            toastText(`${desc} 上傳並部署成功！`, "success");
            await loadMultiverse();
        } else {
            let detail = '上傳失敗';
            try { detail = JSON.parse(xhr.responseText).detail || detail; } catch (_) {}
            toastText(detail, "error");
        }
    });

    xhr.addEventListener('error', function() {
        _mvHideProgress();
        toastText("上傳網路錯誤，請確認伺服器狀態", "error");
    });

    xhr.addEventListener('timeout', function() {
        _mvHideProgress();
        toastText("上傳逾時，請確認網路品質後重試", "error");
    });

    xhr.open('POST', url);
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.timeout = 0; // 不設逾時，讓大檔案有足夠時間
    xhr.send(formData);
};

/** 顯示/更新進度條 */
function _mvShowProgress(pct, label) {
    let overlay = document.getElementById('mv-upload-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'mv-upload-overlay';
        overlay.className = 'sheet-overlay';
        overlay.style.cssText = 'display:flex;';
        overlay.append(h('div', { class: 'sheet mv-progress' },
            h('p', { class: 'card-h', text: '上傳模組包' }),
            h('p', { id: 'mv-prog-label', class: 'w-muted', text: '準備上傳…' }),
            h('div', { class: 'w-bar' }, h('div', { id: 'mv-prog-bar', style: 'width:0%' })),
            h('b', { id: 'mv-prog-pct', class: 'w-big mv-prog-pct', text: '0%' }),
            h('p', { class: 'w-muted mv-hint', text: '上傳完成後伺服器會自動停止並重新部署，請不要關閉這個頁面。' })));
        document.body.appendChild(overlay);
    }
    const bar = document.getElementById('mv-prog-bar');
    const lbl = document.getElementById('mv-prog-label');
    const pctEl = document.getElementById('mv-prog-pct');
    if (bar) bar.style.width = `${pct}%`;
    if (lbl) lbl.textContent = label;
    if (pctEl) pctEl.textContent = `${pct}%`;
}

/** 隱藏進度條 */
function _mvHideProgress() {
    const overlay = document.getElementById('mv-upload-overlay');
    if (overlay) overlay.remove();
}

window.uninstallServerPack = async function() {
    if (!(await axisAsk({ title: '卸載伺服器模組包？', message: '會刪除 mods、config 等資料夾並重啟伺服器；世界存檔（world）會保留。', ok: '卸載', danger: true }))) return;
    
    toastText("正在卸載伺服器模組包，請稍候...", "info");
    
    try {
        const res = await authFetch('/api/minecraft/uninstall-server', { method: 'POST' });
        if (res.ok) {
            toastText("伺服器模組包已成功卸載！", "success");
            await loadMultiverse();
        } else {
            const data = await res.json();
            toastText(data.detail || "卸載失敗", "error");
        }
    } catch (e) {
        toastText("網路錯誤：" + e.message, "error");
    }
};

window.downloadClientPack = function() {
    toastText("開始下載客戶端模組包...", "success");
    window.location.href = window.location.origin + '/static/minecraft-client-pack.zip';
};

