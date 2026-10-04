// Absolute Axis - Dashboard, Metrics & Stats Module
let cpuChart, ramChart;

// Chart.js 需要實際的顏色字串（不認 var(--…)），所以從目前主題的 CSS 變數讀出來
function cssVar(name) {
    return getComputedStyle(document.body).getPropertyValue(name).trim() || '#888888';
}

function initCharts() {
    if (cpuChart) return;
    const ctxCpu = document.getElementById('chart-cpu');
    const ctxRam = document.getElementById('chart-ram');
    if (!ctxCpu || !ctxRam) return;

    const config = (label, color) => ({
        type: 'line',
        data: { labels: Array(30).fill(''), datasets: [{ label: label, data: Array(30).fill(0), borderColor: color, tension: 0.35, fill: true, backgroundColor: color + '22', pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 }] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                y: { min: 0, max: 100, grid: { color: cssVar('--border-color') },
                     ticks: { color: cssVar('--text-muted'), stepSize: 25, callback: (v) => v + '%' } },
                x: { display: false }
            },
            plugins: { legend: { display: false },
                       tooltip: { displayColors: false, callbacks: { label: (c) => `${c.dataset.label} ${Number(c.raw).toFixed(1)}%` } } }
        }
    });

    cpuChart = new Chart(ctxCpu.getContext('2d'), config('CPU %', cssVar('--accent-color')));
    ramChart = new Chart(ctxRam.getContext('2d'), config('RAM %', cssVar('--success-color')));
}

// ==================== 拆分後的三段獨立輪詢 ====================

/**
 * pollMetrics - 高頻（每 5 秒）
 * 取得 CPU、RAM、磁碟、頻寬
 */
async function pollMetrics() {
    try {
        const s = await authFetch('/api/system/metrics');
        if (s.ok) {
            const d = await s.json();

            const cpuVal = document.getElementById('cpu-val');
            const cpuGauge = document.getElementById('cpu-gauge');
            if (cpuVal) cpuVal.innerText = d.cpu_percent.toFixed(1) + '%';
            if (cpuGauge) cpuGauge.style.strokeDashoffset = 125.66 - (d.cpu_percent / 100 * 125.66);

            const ramVal = document.getElementById('ram-val');
            const ramGauge = document.getElementById('ram-gauge');
            if (ramVal) ramVal.innerText = d.ram_percent.toFixed(1) + '%';
            if (ramGauge) ramGauge.style.strokeDashoffset = 125.66 - (d.ram_percent / 100 * 125.66);

            const sLab = document.getElementById('sys-label');
            const sBar = document.getElementById('sys-bar');
            if (sLab) sLab.innerText = `${(d.sys_disk.used/(1024**3)).toFixed(1)}G / ${(d.sys_disk.total/(1024**3)).toFixed(0)}G`;
            if (sBar) sBar.style.width = d.sys_disk.percent + '%';

            const nLab = document.getElementById('nas-label');
            const nBar = document.getElementById('nas-bar');
            if (nLab) nLab.innerText = `${(d.nas_disk.used/(1024**3)).toFixed(1)}G / ${(d.nas_disk.total/(1024**3)).toFixed(0)}G`;
            if (nBar) nBar.style.width = d.nas_disk.percent + '%';

            const ssdVal = document.getElementById('nas-ssd-val');
            const ssdBar = document.getElementById('nas-ssd-bar');
            if (ssdVal) ssdVal.innerText = d.sys_disk.percent.toFixed(1) + '%';
            if (ssdBar) ssdBar.style.width = d.sys_disk.percent + '%';

            const hddVal = document.getElementById('nas-hdd-val');
            const hddBar = document.getElementById('nas-hdd-bar');
            if (hddVal) hddVal.innerText = d.nas_disk.percent.toFixed(1) + '%';
            if (hddBar) hddBar.style.width = d.nas_disk.percent + '%';

            const bwUp = document.getElementById('bw-up');
            const bwDn = document.getElementById('bw-dn');
            if (bwUp) bwUp.innerText = d.bandwidth.up;
            if (bwDn) bwDn.innerText = d.bandwidth.down;

            // 實時數據頁的目前數值（metrics.html）
            const mtCpu = document.getElementById('mt-cpu-now');
            const mtRam = document.getElementById('mt-ram-now');
            if (mtCpu) mtCpu.textContent = Math.round(d.cpu_percent) + '%';
            if (mtRam) mtRam.textContent = Math.round(d.ram_percent) + '%';
            if (cpuChart) {
                cpuChart.data.datasets[0].data.push(d.cpu_percent);
                if (cpuChart.data.datasets[0].data.length > 30) cpuChart.data.datasets[0].data.shift();
                cpuChart.update();
            }
            if (ramChart) {
                ramChart.data.datasets[0].data.push(d.ram_percent);
                if (ramChart.data.datasets[0].data.length > 30) ramChart.data.datasets[0].data.shift();
                ramChart.update();
            }
        }
    } catch (e) {
        console.error("Metrics polling error:", e);
    } finally {
        if (window._metricsTimer) clearTimeout(window._metricsTimer);
        window._metricsTimer = setTimeout(pollMetrics, 5000);
    }
}

/**
 * pollSensors - 中頻（每 30 秒）
 * 取得溫濕度、Minecraft 狀態
 */
async function pollSensors() {
    try {
        const s = await authFetch('/api/system/sensors');
        if (s.ok) {
            const d = await s.json();

            const temp = document.getElementById('sensor-temp');
            const humid = document.getElementById('sensor-humid');
            if (temp) temp.innerText = d.sensors.temp + '°C';
            if (humid) humid.innerText = d.sensors.humid + '%';

            if (d.minecraft) {
                const mcStatus = document.getElementById('mc-status');
                const mcIp = document.getElementById('mc-ip');
                const mcCfg = document.getElementById('mc-config');

                if (mcStatus) {
                    if (d.minecraft.paused) {
                        // 沒人玩、自動暫停省電中；有人連線就會醒來（DeviceHub FR-19c）
                        mcStatus.innerText = '◐ 省電中（有人連線就會醒來）';
                        mcStatus.style.background = 'var(--accent-color)';
                        mcStatus.style.color = 'var(--on-accent)';
                    } else if (d.minecraft.online) {
                        mcStatus.innerText = '● 連線中 (Online)';
                        mcStatus.style.background = 'var(--success-color)';
                        mcStatus.style.color = 'var(--on-accent)';
                    } else {
                        mcStatus.innerText = '○ 離線 (Offline)';
                        mcStatus.style.background = 'var(--off-color)';
                        mcStatus.style.color = 'var(--text-main)';
                    }
                }
                if (mcIp) mcIp.innerText = d.minecraft.ip !== 'Unknown' ? `${d.minecraft.ip}:${d.minecraft.port}` : '--';
                if (mcCfg && d.minecraft.specs) mcCfg.innerText = `配置：${d.minecraft.specs.ram} RAM / ${d.minecraft.specs.cores} Threads`;
            }
        }
    } catch (e) {
        console.error("Sensors polling error:", e);
    } finally {
        if (window._sensorsTimer) clearTimeout(window._sensorsTimer);
        window._sensorsTimer = setTimeout(pollSensors, 30000);
    }
}

/**
 * pollGithub - 低頻（每 120 秒）
 * 取得 GitHub 倉庫狀態（後端已有 120 秒快取）
 */
async function pollGithub() {
    try {
        const s = await authFetch('/api/system/github');
        if (s.ok) {
            const g = await s.json();
            const dot = document.getElementById('gh-dot');
            const repo = document.getElementById('gh-repo');
            const commit = document.getElementById('gh-commit');
            const sTime = document.getElementById('gh-time');
            const stars = document.getElementById('gh-stars');

            if (dot) dot.className = `status-dot ${g.online ? 'online pulse' : ''}`;
            if (repo) repo.innerText = g.repo;
            if (commit) commit.innerText = g.last_commit;
            if (sTime) {
                const now = new Date();
                sTime.innerText = g.online
                    ? `Last Sync: ${now.getHours()}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
                    : 'Last Sync: Offline';
            }
            if (stars) stars.innerText = `⭐ ${g.stars}`;
        }
    } catch (e) {
        console.error("GitHub polling error:", e);
    } finally {
        if (window._githubTimer) clearTimeout(window._githubTimer);
        window._githubTimer = setTimeout(pollGithub, 120000);
    }
}

/**
 * renderLogs - 渲染與過濾日誌
 */
const _LOG_TAGS = [
    ['SECURITY:', 'log-badge-security', '安全警報'],
    ['BROADCAST:', 'log-badge-broadcast', '廣播'],
    ['MC_COMMAND:', 'log-badge-mc', 'MC 指令'],
    ['Admin:', 'log-badge-admin', '管理'],
    ['Cloud storage:', 'log-badge-cloud', '私有雲'],
    ['SYSTEM:', 'log-badge-system', '系統'],
];

function renderLogs(logs) {
    const logBox = document.getElementById('terminal-logs');
    if (!logBox) return;

    const filterText = (document.getElementById('log-search-input')?.value || '').toLowerCase().trim();
    const filtered = logs.filter(x => String(x).toLowerCase().includes(filterText));

    // 紀錄內容含使用者輸入（廣播訊息、上傳檔名…）：只用 textContent，標籤用獨立的 span
    logBox.replaceChildren(...filtered.map(x => {
        const line = String(x);
        // 取最前面出現的類別字樣：動作本身的前綴，而不是使用者訊息裡的字（避免偽裝成「安全警報」）
        let tag = null, i = -1;
        for (const t of _LOG_TAGS) {
            const at = line.indexOf(t[0]);
            if (at !== -1 && (i === -1 || at < i)) { tag = t; i = at; }
        }
        if (!tag) return h('div', { class: 'log-line', text: line });
        return h('div', { class: 'log-line' },
            line.slice(0, i),
            h('span', { class: `log-badge ${tag[1]}`, text: tag[2] }),
            line.slice(i + tag[0].length));
    }));

    if (document.activeElement !== document.getElementById('log-search-input')) {
        logBox.scrollTop = logBox.scrollHeight;
    }
}

function filterLogs() {
    renderLogs(window._cachedLogs || []);
}
window.filterLogs = filterLogs;

/**
 * 服務狀態與稽核日誌輪詢（每 5 秒）
 */
async function pollServices() {
    try {
        const l = await authFetch('/api/system/logs');
        if (l.ok) {
            const logs = await l.json();
            window._cachedLogs = logs;
            renderLogs(logs);
        }

        const sv = await authFetch('/api/services_status');
        if (sv.ok) {
            const svcs = await sv.json();
            const svcList = document.getElementById('svc-list');
            if (svcList) {
                svcList.replaceChildren(...svcs.map(x => h('div', { class: 'svc-row' },
                    h('span', { text: x.name }),
                    h('span', { class: `svc-state ${x.online ? 'ok' : 'bad'}`, text: `● ${x.online ? '正常' : '離線'}` }))));
            }
        }
    } catch (e) {
        console.error("Services polling error:", e);
    } finally {
        if (window._servicesTimer) clearTimeout(window._servicesTimer);
        window._servicesTimer = setTimeout(pollServices, 5000);
    }
}

/**
 * startPolling - 統一入口，啟動全部輪詢
 * 由 app.js 在登入後呼叫
 */
function startPolling() {
    pollMetrics();
    pollSensors();
    pollGithub();
    pollServices();

    // 所有已登入使用者皆顯示系統廣播區塊
    const broadSec = document.getElementById('broadcast-sec');
    if (broadSec) {
        broadSec.style.display = 'flex';
    }

    // 管理者顯示公告發布區塊
    const role = localStorage.getItem('axis_role');
    const isAdmin = (role === 'admin' || role === 'Administrator');
    const annPostSec = document.getElementById('announcement-post-sec');
    if (annPostSec) {
        annPostSec.style.display = isAdmin ? 'flex' : 'none';
    }
    
    // 預載公告列表
    loadAnnouncements();
}

async function loadSpecs() {
    const res = await authFetch('/api/sys_config');
    if (!res.ok) return;
    const s = await res.json();
    const ks = [['作業系統','os'],['Python','python'],['CPU 核心','cpu_cores'],['記憶體','ram_total'],['主機名稱','hostname'],['開機時間','boot_time'],['GPU','gpu']];
    const el = document.getElementById('sys-specs-grid');
    if (!el) return;
    // 設定頁「伺服器規格」：iOS 清單列（名稱／數值），伺服器回傳的字串一律 textContent
    el.replaceChildren(...ks.map(([label, k]) => {
        const row = document.createElement('div');
        row.className = 'ios-row static';
        const l = document.createElement('span');
        l.className = 'ios-label';
        l.textContent = label;
        const v = document.createElement('span');
        v.className = 'ios-value';
        v.textContent = s[k] == null || s[k] === '' ? '—' : String(s[k]);
        row.append(l, v);
        return row;
    }));
}

async function broadCast() {
    const m = document.getElementById('msg-input');
    if (m && m.value) {
        if (!(await axisAsk({ title: '送出廣播訊息？', message: '會寫進稽核日誌，所有登入的使用者都看得到。', ok: '送出' }))) return;
        await authFetch('/api/system/message', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: m.value }) });
        m.value = '';
    }
}

window.switchTerminalTab = function(tab) {
    const tabLogTitle = document.getElementById('tab-log-title');
    const tabAnnTitle = document.getElementById('tab-ann-title');
    const logContent = document.getElementById('terminal-log-content');
    const annContent = document.getElementById('terminal-ann-content');
    const logSearchInput = document.getElementById('log-search-input');
    
    if (tab === 'log') {
        if (tabLogTitle) {
            tabLogTitle.style.color = 'var(--accent-color)';
            tabLogTitle.style.borderBottom = '2px solid var(--accent-color)';
        }
        if (tabAnnTitle) {
            tabAnnTitle.style.color = 'var(--text-muted)';
            tabAnnTitle.style.borderBottom = 'none';
        }
        if (logContent) logContent.style.display = 'flex';
        if (annContent) annContent.style.display = 'none';
        if (logSearchInput) logSearchInput.style.display = 'block';
    } else if (tab === 'ann') {
        if (tabLogTitle) {
            tabLogTitle.style.color = 'var(--text-muted)';
            tabLogTitle.style.borderBottom = 'none';
        }
        if (tabAnnTitle) {
            tabAnnTitle.style.color = 'var(--accent-color)';
            tabAnnTitle.style.borderBottom = '2px solid var(--accent-color)';
        }
        if (logContent) logContent.style.display = 'none';
        if (annContent) annContent.style.display = 'flex';
        if (logSearchInput) logSearchInput.style.display = 'none';
        
        loadAnnouncements();
    }
};

async function loadAnnouncements() {
    const annBox = document.getElementById('terminal-announcements');
    if (!annBox) return;
    const note = (text, cls) => annBox.replaceChildren(h('div', { class: cls, text }));

    try {
        const res = await authFetch('/api/system/announcements');
        if (!res.ok) {
            note('無法載入公告。', 'ann-note bad');
            return;
        }
        const anns = await res.json();
        if (!anns.length) {
            note('目前沒有公告。', 'ann-note');
            return;
        }
        annBox.replaceChildren(...anns.map(x => h('div', { class: 'ann-item' },
            h('div', { class: 'ann-meta' },
                h('span', { text: `公告・${x.author}` }),
                h('span', { text: x.timestamp })),
            h('div', { class: 'ann-body', text: x.content }))));
        annBox.scrollTop = annBox.scrollHeight;
    } catch (e) {
        console.error("Failed to load announcements:", e);
        note('載入公告時發生錯誤。', 'ann-note bad');
    }
}

window.loadAnnouncements = loadAnnouncements;

window.publishAnnouncement = async function() {
    const input = document.getElementById('ann-input');
    if (!input) return;
    
    const content = input.value.trim();
    if (!content) {
        toastText("請輸入公告內容！", "error");
        return;
    }
    
    if (!(await axisAsk({ title: '發布這則公告？', message: '所有登入的使用者都會看到。', ok: '發布' }))) return;
    
    try {
        const res = await authFetch('/api/system/announcements', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        
        if (res.ok) {
            toastText("公告發布成功！", "success");
            input.value = '';
            await loadAnnouncements();
        } else {
            const err = await res.json().catch(() => ({}));
            toastText(typeof err.detail === 'string' ? err.detail : "發布公告失敗", "error");
        }
    } catch (e) {
        toastText("網路錯誤：" + e.message, "error");
    }
};
