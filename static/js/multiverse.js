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
    } catch (e) {
        _mvRenderError(`連線失敗：${e.message}`);
    }
}

/**
 * 渲染伺服器狀態至各 DOM 元素。
 */
function _mvRenderStatus(data) {
    const online = data.online;

    // --- 頂部橫幅 ---
    const dot = document.getElementById('mv-banner-dot');
    const title = document.getElementById('mv-banner-title');
    const sub = document.getElementById('mv-banner-sub');
    const banner = document.getElementById('mv-status-banner');

    if (online) {
        dot.style.background = '#4CAF50';
        dot.style.boxShadow = '0 0 8px rgba(76,175,80,0.7)';
        title.textContent = '🌌 Absolute-Axis MC — 伺服器線上';
        sub.textContent = '連線正常，Minecraft Java Edition 運行中';
        banner.style.borderLeftColor = '#4CAF50';
    } else {
        dot.style.background = '#da3633';
        dot.style.boxShadow = '0 0 8px rgba(218,54,51,0.7)';
        title.textContent = '🌌 Absolute-Axis MC — 伺服器離線';
        sub.textContent = 'TCP 連線失敗，服務可能已停止或正在引導中';
        banner.style.borderLeftColor = '#da3633';
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
    _mvSet('mv-wan', data.connection?.address_wan || '--');

    // --- 硬體規格 ---
    _mvSet('mv-ram', data.specs?.ram || '--');
    _mvSet('mv-jvm', data.specs?.jvm_heap || '--');
    _mvSet('mv-cpu', `${data.specs?.cpu_threads || '--'} Threads`);
    _mvSet('mv-container', data.specs?.container || '--');

    // --- 脈搏狀態環 ---
    const ring = document.getElementById('mv-pulse-ring');
    const ringLabel = document.getElementById('mv-pulse-label');
    if (online) {
        ring.style.border = '3px solid #4CAF50';
        ring.style.boxShadow = '0 0 12px rgba(76,175,80,0.5)';
        ring.style.animation = 'mv-pulse-anim 2s infinite';
        ringLabel.textContent = 'ONLINE';
        ringLabel.style.color = '#4CAF50';
    } else {
        ring.style.border = '3px solid #da3633';
        ring.style.boxShadow = 'none';
        ring.style.animation = 'none';
        ringLabel.textContent = 'OFFLINE';
        ringLabel.style.color = '#da3633';
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
    if (sub) sub.textContent = `⚠️ ${msg}`;
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
    navigator.clipboard.writeText(el.textContent).then(() => {
        const orig = el.style.color;
        el.style.color = '#4CAF50';
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

    // 立即在 log 顯示送出記錄
    const ts = new Date().toLocaleTimeString('zh-TW');
    const pendingLine = document.createElement('div');
    pendingLine.innerHTML = `<span style="color:#8b949e">[${ts}]</span> <span style="color:#bd93f9">></span> <span style="color:#fff;">${escapeHtml(command)}</span> <span style="color:#8b949e">— 發送中...</span>`;
    log.appendChild(pendingLine);
    log.scrollTop = log.scrollHeight;
    input.value = '';

    try {
        const res = await authFetch('/api/minecraft/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });

        const data = await res.json();

        if (res.ok) {
            pendingLine.innerHTML = `<span style="color:#8b949e">[${ts}]</span> <span style="color:#4CAF50">✓</span> <span style="color:#7ee787;">${escapeHtml(command)}</span>`;
        } else {
            pendingLine.innerHTML = `<span style="color:#8b949e">[${ts}]</span> <span style="color:#da3633">✗</span> <span style="color:#f85149;">${escapeHtml(command)}</span> — ${data.detail || '未知錯誤'}`;
        }
    } catch (e) {
        pendingLine.innerHTML = `<span style="color:#8b949e">[${ts}]</span> <span style="color:#da3633">✗</span> <span style="color:#f85149;">${escapeHtml(command)}</span> — 網路錯誤：${e.message}`;
    }
    log.scrollTop = log.scrollHeight;
};

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 注入 CSS 動畫（僅注入一次）
if (!document.getElementById('mv-style')) {
    const style = document.createElement('style');
    style.id = 'mv-style';
    style.textContent = `
        @keyframes mv-pulse-anim {
            0% { box-shadow: 0 0 0 0 rgba(76,175,80,0.4); }
            70% { box-shadow: 0 0 0 10px rgba(76,175,80,0); }
            100% { box-shadow: 0 0 0 0 rgba(76,175,80,0); }
        }
        .mv-info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .mv-label {
            font-size: 0.7rem;
            font-weight: 800;
            color: var(--text-muted);
        }
        .mv-value {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--text-main);
            text-align: right;
            max-width: 60%;
        }
        #mv-cmd-log::-webkit-scrollbar { width: 6px; }
        #mv-cmd-log::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
    `;
    document.head.appendChild(style);
}
