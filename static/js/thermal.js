/**
 * Absolute Axis - Thermal Control Manager
 * 處理硬體溫度監控與風扇 PWM 控制邏輯
 */
const ThermalManager = {
    state: {
        fans: [],
        sensors: [],
        timer: null,
        isChanging: false
    },

    async init() {
        console.log("ThermalManager: Initializing...");
        await this.refresh();
        this.startPolling();
    },

    async refresh() {
        if (this.state.isChanging) return;
        try {
            const res = await authFetch('/api/thermal/status');
            const data = await res.json();
            this.state.fans = data.fans || [];
            this.state.sensors = data.sensors || [];
            this.render();
        } catch (err) {
            console.error("Failed to fetch thermal status:", err);
        }
    },

    startPolling() {
        if (this.state.timer) clearInterval(this.state.timer);
        this.state.timer = setInterval(() => this.refresh(), 3000); // 3秒更新一次
    },

    stopPolling() {
        if (this.state.timer) {
            clearInterval(this.state.timer);
            this.state.timer = null;
        }
    },

    render() {
        // 1. 渲染溫度計
        const tGrid = document.getElementById('thermal-temps-grid');
        if (tGrid) {
            tGrid.innerHTML = this.state.sensors.map(s => `
                <div class="stat-card" style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03);">
                    <div style="font-size:0.85rem; opacity:0.7;">${s.name}</div>
                    <div style="font-size:1.2rem; font-weight:700; color:${s.value > 65 ? '#ff4d4d' : '#2ecc71'}">${s.value}°C</div>
                </div>
            `).join('');
        }

        // 2. 渲染風扇列表
        const fList = document.getElementById('thermal-fans-list');
        if (fList) {
            fList.innerHTML = this.state.fans.map(f => `
                <div class="card" style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); padding:1rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                        <div>
                            <div style="font-weight:700; font-size:1rem;">Fan #${f.index} (${f.hw})</div>
                            <div style="font-size:0.8rem; opacity:0.6;">當前轉速: <span style="color:var(--accent-color)">${f.rpm} RPM</span></div>
                        </div>
                        <div style="display:flex; gap:0.5rem;">
                            <button class="btn ${f.mode === 'auto' ? 'btn-primary' : 'btn-outline'}" 
                                    style="padding:4px 10px; font-size:0.75rem;" 
                                    onclick="ThermalManager.setMode('${f.path}', '${f.index}', 'auto')">Auto</button>
                            <button class="btn ${f.mode === 'manual' ? 'btn-primary' : 'btn-outline'}" 
                                    style="padding:4px 10px; font-size:0.75rem;" 
                                    onclick="ThermalManager.setMode('${f.path}', '${f.index}', 'manual')">Manual</button>
                        </div>
                    </div>
                    
                    <div style="display:flex; align-items:center; gap:1rem; opacity:${f.mode === 'auto' ? '0.3' : '1'}; pointer-events:${f.mode === 'auto' ? 'none' : 'auto'}">
                        <span style="font-size:0.8rem; width:40px;">PWM</span>
                        <input type="range" min="0" max="255" value="${f.pwm}" 
                               style="flex:1; accent-color:var(--accent-color);" 
                               oninput="this.nextElementSibling.innerText = this.value"
                               onchange="ThermalManager.setPWM('${f.path}', '${f.index}', this.value)">
                        <span style="font-size:0.8rem; width:30px; text-align:right;">${f.pwm}</span>
                    </div>
                </div>
            `).join('');
        }
    },

    async setMode(path, index, mode) {
        try {
            await authFetch('/api/thermal/set', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path, index, mode})
            });
            showToast(`已切換為 ${mode === 'auto' ? '自動' : '手動'} 模式`);
            this.refresh();
        } catch (err) {
            showToast("模式切換失敗", "error");
        }
    },

    async setPWM(path, index, value) {
        this.state.isChanging = true;
        try {
            await authFetch('/api/thermal/set', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path, index, value, mode: 'manual'})
            });
        } catch (err) {
            showToast("轉速設定失敗", "error");
        } finally {
            setTimeout(() => { this.state.isChanging = false; }, 1000);
        }
    }
};

window.ThermalManager = ThermalManager;
