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
                    dlBtn.innerHTML = '📥 下載客戶端模組包';
                } else {
                    dlBtn.disabled = true;
                    dlBtn.innerHTML = '❌ 尚未上傳客戶端模組包';
                }
            }
            
            // 管理端按鈕權限顯示
            const role = localStorage.getItem('axis_role');
            const isAdmin = (role === 'admin' || role === 'Administrator');
            const editDescBtn = document.getElementById('mv-edit-desc-btn');
            const adminControls = document.getElementById('mv-admin-pack-controls');
            
            if (editDescBtn) editDescBtn.style.display = isAdmin ? 'block' : 'none';
            if (adminControls) adminControls.style.display = isAdmin ? 'flex' : 'none';
        }
    } catch (e) {
        console.error("載入模組包資訊失敗:", e);
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
    const wanEl = document.getElementById('mv-wan');
    if (wanEl) {
        wanEl.textContent = data.connection?.address_wan || '--';
        wanEl.setAttribute('data-copy', data.connection?.address_wan_real || '');
    }
    _mvSet('mv-ddns', data.connection?.address_ddns || '--');

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
    const textToCopy = el.getAttribute('data-copy') || el.textContent;
    navigator.clipboard.writeText(textToCopy).then(() => {
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
        if (display) display.style.display = 'block';
        if (editArea) editArea.style.display = 'none';
        if (editBtn) editBtn.style.display = 'block';
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
            if (typeof showToast === 'function') showToast("模組包說明已保存", "success");
            toggleEditDesc(false);
            await loadMultiverseInfo();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "保存失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("網路錯誤：" + e.message, "error");
    }
};

window.triggerUpload = function(type) {
    window._mvUploadType = type;
    const fileInput = document.getElementById('mv-file-input');
    if (fileInput) {
        fileInput.value = ''; // Reset
        fileInput.click();
    }
};

window.handleFileSelected = async function(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const type = window._mvUploadType;
    
    if (!file.name.endsWith('.zip')) {
        if (typeof showToast === 'function') showToast("僅接受 .zip 壓縮包！", "warning");
        return;
    }
    
    const url = type === 'server' ? '/api/minecraft/upload-server' : '/api/minecraft/upload-client';
    const desc = type === 'server' ? '伺服器端包' : '客戶端包';
    
    if (typeof showToast === 'function') showToast(`正在上傳 ${desc}，大檔案請耐心等候...`, "info");
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const token = localStorage.getItem('axis_token');
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const data = await res.json();
        if (res.ok) {
            if (typeof showToast === 'function') showToast(`${desc} 上傳並部署成功！`, "success");
            await loadMultiverse();
        } else {
            if (typeof showToast === 'function') showToast(data.detail || "上傳失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("上傳網路錯誤：" + e.message, "error");
    }
};

window.uninstallServerPack = async function() {
    const ok = confirm("警告：您確定要卸載伺服器模組包嗎？這將刪除 mods、config 等資料夾並重啟伺服器（地圖存檔 world 將會保留）。");
    if (!ok) return;
    
    if (typeof showToast === 'function') showToast("正在卸載伺服器模組包，請稍候...", "info");
    
    try {
        const res = await authFetch('/api/minecraft/uninstall-server', { method: 'POST' });
        if (res.ok) {
            if (typeof showToast === 'function') showToast("伺服器模組包已成功卸載！", "success");
            await loadMultiverse();
        } else {
            const data = await res.json();
            if (typeof showToast === 'function') showToast(data.detail || "卸載失敗", "error");
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast("網路錯誤：" + e.message, "error");
    }
};

window.downloadClientPack = function() {
    if (typeof showToast === 'function') showToast("開始下載客戶端模組包...", "success");
    window.location.href = window.location.origin + '/static/minecraft-client-pack.zip';
};

