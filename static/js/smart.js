/**
 * Absolute Axis - Smart Control Module
 * Handles ESP32 environment data rendering (Blynk) and, for administrators, the DeviceHub
 * home tab (devicehub.js): server power, devices, VMs, alerts.
 */

// 自動刷新 Timer handle
let _smartRefreshTimer = null;

/**
 * 載入並渲染智慧宅控頁面數據。
 * 由 ui.js switchView('smart') 以及定時自動刷新觸發。
 */
async function loadSmart() {
    // 確保只在當前頁面為 smart 時才進行刷新
    const currentActiveView = document.querySelector('.view-section.active');
    if (!currentActiveView || currentActiveView.id !== 'view-smart') {
        if (_smartRefreshTimer) {
            clearTimeout(_smartRefreshTimer);
            _smartRefreshTimer = null;
        }
        return;
    }

    try {
        const res = await authFetch('/api/system_status');
        if (!res.ok) {
            _smartRenderError(`API 錯誤：HTTP ${res.status}`);
            return;
        }
        const data = await res.json();
        _smartRenderStatus(data);
    } catch (e) {
        _smartRenderError(`連線失敗：${e.message}`);
    } finally {
        // DeviceHub 跟著同一個週期刷新（只有管理員會發請求；只在首頁可見時）
        if (typeof loadDeviceHub === 'function') loadDeviceHub();
        // 排程下一次的數據刷新 (5 秒週期)
        if (_smartRefreshTimer) clearTimeout(_smartRefreshTimer);
        _smartRefreshTimer = setTimeout(loadSmart, 5000);
    }
}

/**
 * 渲染溫濕度與環境評估狀態至 DOM 元素。
 */
function _smartRenderStatus(data) {
    if (!data || !data.sensors) {
        _smartRenderError('無感測器數據');
        return;
    }

    const temp = parseFloat(data.sensors.temp);
    const humid = parseFloat(data.sensors.humid);

    // 1. 填入實時數據
    const tempEl = document.getElementById('smart-sensor-temp');
    const humidEl = document.getElementById('smart-sensor-humid');
    const updateEl = document.getElementById('smart-last-update');
    const blynkStatusEl = document.getElementById('smart-blynk-status');
    const blynkDotEl = document.getElementById('smart-blynk-dot');

    if (tempEl) tempEl.textContent = `${temp.toFixed(1)} °C`;
    if (humidEl) humidEl.textContent = `${humid.toFixed(1)} %`;
    if (updateEl) updateEl.textContent = new Date().toLocaleTimeString('zh-TW');

    // 2. 判斷 API 異常顯示 (99.9 代表後端 API 回傳 Blynk 異常, 88.8 代表連線異常)
    if (temp === 99.9 || temp === 88.8) {
        if (blynkStatusEl) {
            blynkStatusEl.textContent = temp === 99.9 ? '● Blynk 雲端 API 異常 (Blynk API Error)' : '● ESP32 聯網逾時 (Timeout)';
            blynkStatusEl.style.color = 'var(--danger-color)';
        }
        if (blynkDotEl) {
            blynkDotEl.style.background = 'var(--danger-color)';
            blynkDotEl.style.boxShadow = '0 0 8px rgba(218,54,51,0.7)';
        }
    } else {
        if (blynkStatusEl) {
            blynkStatusEl.textContent = '● 連線正常 (CONNECTED)';
            blynkStatusEl.style.color = 'var(--success-color)';
        }
        if (blynkDotEl) {
            blynkDotEl.style.background = '#2ecc71';
            blynkDotEl.style.boxShadow = '0 0 8px rgba(46,204,113,0.7)';
        }
    }

    // 3. 計算體感溫度 (Standard meteorological feels-like formula)
    // feelsLike = T + 0.33 * e - 4.0 (其中 e 為水氣壓，單位 hPa)
    const e = (humid / 100) * 6.105 * Math.exp((17.27 * temp) / (237.7 + temp));
    const feelsLike = temp + 0.33 * e - 4.0;

    const feelsEl = document.getElementById('smart-feels-temp');
    if (feelsEl) feelsEl.textContent = `${feelsLike.toFixed(1)} °C`;

    // 4. 環境舒適度評估與排風連動建議
    const comfortEl = document.getElementById('smart-comfort-status');
    if (comfortEl) {
        if (temp === 99.9 || temp === 88.8) {
            comfortEl.textContent = '無法評估';
            comfortEl.style.background = '#444';
            comfortEl.style.color = '#fff';
        } else if (temp > 28) {
            comfortEl.textContent = '環境偏熱';
            comfortEl.style.background = 'rgba(231,76,60,0.15)';
            comfortEl.style.color = '#e74c3c';
        } else if (temp < 18) {
            comfortEl.textContent = '環境偏冷';
            comfortEl.style.background = 'rgba(52,152,219,0.15)';
            comfortEl.style.color = '#3498db';
        } else if (humid > 65) {
            comfortEl.textContent = '環境潮濕';
            comfortEl.style.background = 'rgba(242,170,31,0.15)';
            comfortEl.style.color = '#f2aa1f';
        } else {
            comfortEl.textContent = '舒適宜人';
            comfortEl.style.background = 'rgba(46,204,113,0.15)';
            comfortEl.style.color = '#2ecc71';
        }
    }
}

/**
 * 渲染載入失敗錯誤。
 */
function _smartRenderError(msg) {
    const tempEl = document.getElementById('smart-sensor-temp');
    const humidEl = document.getElementById('smart-sensor-humid');
    const blynkStatusEl = document.getElementById('smart-blynk-status');
    const blynkDotEl = document.getElementById('smart-blynk-dot');

    if (tempEl) tempEl.textContent = '--';
    if (humidEl) humidEl.textContent = '--';
    if (blynkStatusEl) {
        blynkStatusEl.textContent = `● ${msg}`;
        blynkStatusEl.style.color = 'var(--danger-color)';
    }
    if (blynkDotEl) {
        blynkDotEl.style.background = 'var(--danger-color)';
        blynkDotEl.style.boxShadow = 'none';
    }
}

// 監聽全局視圖切換事件，實現節能的定時器控制與即時加載
document.addEventListener('view-switched', (e) => {
    if (e.detail.view === 'smart') {
        loadSmart();
    } else {
        if (_smartRefreshTimer) {
            clearTimeout(_smartRefreshTimer);
            _smartRefreshTimer = null;
        }
    }
});

// ==========================================
// 內部頁籤切換邏輯 (首頁 / 數據 / 裝置)
// ==========================================
window.switchSmartTab = function(tabId) {
    // 隱藏所有內容
    document.querySelectorAll('.smart-tab-content').forEach(el => el.style.display = 'none');
    // 取消所有按鈕的 active
    document.querySelectorAll('.smart-tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = '';
        btn.style.color = '';
    });
    
    // 顯示目標內容
    document.getElementById(`smart-tab-${tabId}`).style.display = 'block';
    
    // 設定目標按鈕 active 樣式
    const activeBtn = document.querySelector(`.smart-tab-btn[data-tab="${tabId}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.style.background = 'var(--accent-color)';
        activeBtn.style.color = '#fff';
    }

    // 若切換到數據頁，初始化圖表
    if (tabId === 'data' && !window._smartChartsInitialized) {
        initSmartCharts();
    }

    // 回到首頁：立即刷新 DeviceHub
    if (tabId === 'home' && typeof loadDeviceHub === 'function') {
        loadDeviceHub();
    }
};

// ==========================================
// 圖表繪製與模擬數據邏輯 (Chart.js)
// ==========================================
let _smartCharts = {};
window._smartChartsInitialized = false;

function generateMockData(count, min, max, base) {
    let data = [];
    let current = base;
    for (let i = 0; i < count; i++) {
        current += (Math.random() - 0.5) * ((max - min) * 0.1);
        if (current > max) current = max;
        if (current < min) current = min;
        data.push(current.toFixed(2));
    }
    return data;
}

function generateLabels(count, intervalMinutes) {
    let labels = [];
    let now = new Date();
    for (let i = count - 1; i >= 0; i--) {
        let t = new Date(now.getTime() - (i * intervalMinutes * 60000));
        labels.push(t.toLocaleTimeString('zh-TW', {hour: '2-digit', minute:'2-digit'}));
    }
    return labels;
}

window.initSmartCharts = function() {
    if (typeof Chart === 'undefined') {
        console.error("Chart.js not loaded!");
        return;
    }

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'var(--text-muted)' } },
            y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'var(--text-muted)' } }
        },
        elements: { point: { radius: 0 } },
        interaction: { intersect: false, mode: 'index' },
    };

    const count = 30;
    const labels = generateLabels(count, 30); // 每 30 分鐘一個點

    const createChart = (canvasId, label, color, min, max, base) => {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: generateMockData(count, min, max, base),
                    borderColor: color,
                    backgroundColor: color + '20',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }]
            },
            options: commonOptions
        });
    };

    _smartCharts['temp'] = createChart('chart-temp', '溫度', '#e74c3c', 20, 35, 27);
    _smartCharts['humid'] = createChart('chart-humid', '濕度', '#3498db', 40, 80, 60);
    _smartCharts['co2'] = createChart('chart-co2', 'CO2', '#f1c40f', 400, 1000, 600);
    _smartCharts['tvoc'] = createChart('chart-tvoc', 'TVOC', '#9b59b6', 50, 500, 150);
    _smartCharts['current'] = createChart('chart-current', '電流', '#2ecc71', 0, 15000, 10000);

    window._smartChartsInitialized = true;
};

window.updateSmartCharts = function(days) {
    if (!window._smartChartsInitialized) return;
    const count = days === '3d' ? 30 : 50;
    const interval = days === '3d' ? 30 : 60; // 30 min vs 1 hour
    const labels = generateLabels(count, interval);

    const updateSingleChart = (key, min, max, base) => {
        if (_smartCharts[key]) {
            _smartCharts[key].data.labels = labels;
            _smartCharts[key].data.datasets[0].data = generateMockData(count, min, max, base);
            _smartCharts[key].update();
        }
    };

    updateSingleChart('temp', 20, 35, 27);
    updateSingleChart('humid', 40, 80, 60);
    updateSingleChart('co2', 400, 1000, 600);
    updateSingleChart('tvoc', 50, 500, 150);
    updateSingleChart('current', 0, 15000, 10000);
};

// 注入專用樣式
if (!document.getElementById('smart-style')) {
    const style = document.createElement('style');
    style.id = 'smart-style';
    style.textContent = `
        .smart-info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .smart-label {
            font-size: 0.72rem;
            font-weight: 800;
            color: var(--text-muted);
        }
        .smart-value {
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--text-main);
            text-align: right;
        }
    `;
    document.head.appendChild(style);
}
