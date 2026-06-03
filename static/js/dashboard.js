// Absolute Axis - Dashboard, Metrics & Stats Module
let cpuChart, ramChart;

function initCharts() {
    if (cpuChart) return;
    const ctxCpu = document.getElementById('chart-cpu');
    const ctxRam = document.getElementById('chart-ram');
    if (!ctxCpu || !ctxRam) return;

    const config = (label, color) => ({
        type: 'line',
        data: { labels: Array(30).fill(''), datasets: [{ label: label, data: Array(30).fill(0), borderColor: color, tension: 0.3, fill: true, backgroundColor: color + '11', pointRadius: 0, borderWidth: 2 }] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: { y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' } }, x: { display: false } },
            plugins: { legend: { display: false } }
        }
    });

    cpuChart = new Chart(ctxCpu.getContext('2d'), config('CPU %', '#00d2ff'));
    ramChart = new Chart(ctxRam.getContext('2d'), config('RAM %', '#00ff88'));
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
                    if (d.minecraft.online) {
                        mcStatus.innerText = '● 連線中 (Online)';
                        mcStatus.style.background = 'var(--success-color)';
                        mcStatus.style.color = '#000';
                    } else {
                        mcStatus.innerText = '○ 離線 (Offline)';
                        mcStatus.style.background = '#444';
                        mcStatus.style.color = '#fff';
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
function renderLogs(logs) {
    const logBox = document.getElementById('terminal-logs');
    if (!logBox) return;

    const filterText = (document.getElementById('log-search-input')?.value || '').toLowerCase().trim();
    const filtered = logs.filter(x => x.toLowerCase().includes(filterText));

    logBox.innerHTML = filtered.map(x => {
        let content = x;
        let badgeClass = '';
        let typeLabel = '';

        if (x.includes('SECURITY:')) {
            badgeClass = 'log-badge-security';
            typeLabel = '安全警報';
        } else if (x.includes('BROADCAST:')) {
            badgeClass = 'log-badge-broadcast';
            typeLabel = '廣播';
        } else if (x.includes('MC_COMMAND:')) {
            badgeClass = 'log-badge-mc';
            typeLabel = 'MC 指令';
        } else if (x.includes('Admin:')) {
            badgeClass = 'log-badge-admin';
            typeLabel = '管理';
        } else if (x.includes('Cloud storage:')) {
            badgeClass = 'log-badge-cloud';
            typeLabel = '私有雲';
        } else if (x.includes('SYSTEM:')) {
            badgeClass = 'log-badge-system';
            typeLabel = '系統';
        }

        if (badgeClass) {
            content = content.replace(/(SECURITY:|BROADCAST:|MC_COMMAND:|Admin:|Cloud storage:|SYSTEM:)/, `<span class="log-badge ${badgeClass}">${typeLabel}</span>`);
        }

        return `<div style="margin-bottom:6px; line-height:1.6; word-break:break-all;">${content}</div>`;
    }).join('');

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
                svcList.innerHTML = svcs.map(x => `
                    <div style="display:flex;justify-content:space-between;padding:12px;background:var(--bg-color);border-radius:8px;margin-bottom:8px;border:1px solid var(--border-color);font-size:0.85rem;">
                        <span>${x.name}</span>
                        <span style="color:${x.online?'var(--success-color)':'var(--danger-color)'};font-weight:700;">● ${x.online?'Running':'Offline'}</span>
                    </div>
                `).join('');
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
}

async function loadSpecs() {
    const res = await authFetch('/api/sys_config');
    if (!res.ok) return;
    const s = await res.json();
    const ks = [['OS','os'],['PYTHON','python'],['CPU','cpu_cores'],['RAM','ram_total'],['HOST','hostname'],['UP','boot_time'],['GPU','gpu']];
    const el = document.getElementById('sys-specs-grid');
    if (el) {
        el.innerHTML = ks.map(([l,k]) => `
            <div style="background:var(--bg-color);padding:15px;border-radius:8px;border:1px solid var(--border-color);">
                <div style="font-size:0.6rem;color:var(--text-muted);font-weight:800;margin-bottom:5px;">${l}</div>
                <div style="font-size:0.85rem;font-weight:600;color:var(--text-main);">${s[k]}</div>
            </div>
        `).join('');
    }
}

async function broadCast() {
    const m = document.getElementById('msg-input');
    if (m && m.value) {
        const ok = confirm("您確定要發送此系統廣播訊息嗎？");
        if (!ok) return;
        await authFetch('/api/system/message', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: m.value }) });
        m.value = '';
    }
}
