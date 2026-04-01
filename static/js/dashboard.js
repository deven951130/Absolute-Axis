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

async function startPolling() {
    try {
        const s = await authFetch('/api/system_status');
        if (s.ok) {
            const d = await s.json();
            
            // 儀表盤更新
            const cpuVal = document.getElementById('cpu-val');
            const cpuGauge = document.getElementById('cpu-gauge');
            if (cpuVal) cpuVal.innerText = d.cpu_percent.toFixed(1) + '%';
            if (cpuGauge) cpuGauge.style.strokeDashoffset = 125.66 - (d.cpu_percent / 100 * 125.66);

            const ramVal = document.getElementById('ram-val');
            const ramGauge = document.getElementById('ram-gauge');
            if (ramVal) ramVal.innerText = d.ram_percent.toFixed(1) + '%';
            if (ramGauge) ramGauge.style.strokeDashoffset = 125.66 - (d.ram_percent / 100 * 125.66);
            
            // 磁碟監管
            const sLab = document.getElementById('sys-label');
            const sBar = document.getElementById('sys-bar');
            if (sLab) sLab.innerText = `${(d.sys_disk.used/(1024**3)).toFixed(1)}G / ${(d.sys_disk.total/(1024**3)).toFixed(0)}G`;
            if (sBar) sBar.style.width = d.sys_disk.percent + '%';

            const nLab = document.getElementById('nas-label');
            const nBar = document.getElementById('nas-bar');
            if (nLab) nLab.innerText = `${(d.nas_disk.used/(1024**3)).toFixed(1)}G / ${(d.nas_disk.total/(1024**3)).toFixed(0)}G`;
            if (nBar) nBar.style.width = d.nas_disk.percent + '%';
            
            const bwUp = document.getElementById('bw-up');
            const bwDn = document.getElementById('bw-dn');
            if (bwUp) bwUp.innerText = d.bandwidth.up;
            if (bwDn) bwDn.innerText = d.bandwidth.down;

            const temp = document.getElementById('sensor-temp');
            const humid = document.getElementById('sensor-humid');
            if (temp) temp.innerText = d.sensors.temp + '°C';
            if (humid) humid.innerText = d.sensors.humid + '%';

            // 圖表更新
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

        // 終端紀錄 (修復輪詢與同步)
        const l = await authFetch('/api/system/logs');
        if (l.ok) {
            const logs = await l.json();
            const logBox = document.getElementById('terminal-logs');
            if (logBox) {
                logBox.innerHTML = logs.map(x => `<div>${x}</div>`).join('');
                logBox.scrollTop = logBox.scrollHeight;
            }
        }

        // 服務狀態
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
        console.error("Polling error:", e);
    }
    setTimeout(startPolling, 3000);
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
        await authFetch('/api/system/message', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: m.value }) });
        m.value = '';
    }
}
