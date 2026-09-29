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
            blynkDotEl.style.boxShadow = '0 0 8px color-mix(in srgb, var(--danger-color) 70%, transparent)';
        }
    } else {
        if (blynkStatusEl) {
            blynkStatusEl.textContent = '● 連線正常 (CONNECTED)';
            blynkStatusEl.style.color = 'var(--success-color)';
        }
        if (blynkDotEl) {
            blynkDotEl.style.background = 'var(--success-color)';
            blynkDotEl.style.boxShadow = '0 0 8px color-mix(in srgb, var(--success-color) 70%, transparent)';
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
            comfortEl.style.background = 'var(--off-color)';
            comfortEl.style.color = 'var(--text-main)';
        } else if (temp > 28) {
            comfortEl.textContent = '環境偏熱';
            comfortEl.style.background = 'color-mix(in srgb, var(--danger-color) 15%, transparent)';
            comfortEl.style.color = 'var(--danger-color)';
        } else if (temp < 18) {
            comfortEl.textContent = '環境偏冷';
            comfortEl.style.background = 'var(--accent-soft)';
            comfortEl.style.color = 'var(--accent-color)';
        } else if (humid > 65) {
            comfortEl.textContent = '環境潮濕';
            comfortEl.style.background = 'color-mix(in srgb, var(--warning-color) 15%, transparent)';
            comfortEl.style.color = 'var(--warning-color)';
        } else {
            comfortEl.textContent = '舒適宜人';
            comfortEl.style.background = 'color-mix(in srgb, var(--success-color) 15%, transparent)';
            comfortEl.style.color = 'var(--success-color)';
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
        activeBtn.style.color = 'var(--on-accent)';
    }

    // 若切換到數據頁，初始化圖表
    // 歷史：DeviceHub 的真實紀錄（history.js）
    if (tabId === 'data' && typeof loadSmartHistory === 'function') {
        loadSmartHistory();
    }

    // 回到首頁：立即刷新 DeviceHub
    if (tabId === 'home' && typeof loadDeviceHub === 'function') {
        loadDeviceHub();
    }

    // 綁定裝置：DeviceHub 的裝置帳號（binding.js）
    if (tabId === 'devices' && typeof loadDeviceBinding === 'function') {
        loadDeviceBinding();
    }
};
