# Absolute Axis 更新日誌 (Update Logs)

### [V18] - 2026-04-03
#### 【佈局重構：側邊選單捲軸定案修復】
- **結構手術**：解耦 Logo 區與導覽區，建立 `.sidebar-nav-container` 獨立滾動容器。
- **Flexbox 硬化**：強制讓 Logo 區不縮放 (`flex-shrink: 0`)，徹底消除空間爭奪。
- **捲軸顯化**：將 8px 主題色捲軸精確掛載至內層容器。
- **全域同步**：全面升級 CSS/JS 快取版本號至 V18。

## [2026-04-03] - 系統全資產遷移準備
### **遷移設施 (Migration Infrastructure)**
- **金級鏡像封裝 (Golden Image Packing)**：完成全機代碼、SQLite 資料庫與 NAS 存儲目錄的 1:1 密封打包。
- **自解壓復原腳本 (Bootstrap Script)**：注入 `restore.sh` 以支援全新 Ubuntu 的一鍵依賴安裝與 Tunnel 註冊。
- **跨平台計畫對接**：完成遷移路徑規劃，確保資料零位移與連線無縫。

## [2026-04-02] - 遠端存取前路強固與 UI 機能優化
### **存取配置修正 (Remote Access Optimization)**
- **隧道拓點清洗**：移除所有實驗性子網域 (`app-axis`)，回歸單一主域 `absoluteaxis.dpdns.org`。
- **Ingress 全路徑重置**：精確校準 `cloudflared` 守護行程，移除路徑過濾規則 (`^/blog`)。
- **雙路徑兼容 (Dual-Path Logic)**：同時開啟 Root 與 WWW 子網域映射，修復因習慣輸入 `www` 導致的連線問題。
- **三維稽核診斷**：完成從伺服器內部到外部 TLS 握手的完整診斷，確認隧道聯網能力 100% 正常。

### **UI 與視覺系統優化 (UI & Aesthetics)**
- **頭像同步機制重構**：實作 `app.js` 之中的同步邏輯，確保「導覽列頭像」與「使用者彈窗頭像」即時聯動。
- **CSS 語義化變數標準化**：於 `index.css` 定義並引用 `--success-color`（成功綠）與 `--danger-color`（危險紅），統一全局狀態色值。
- **彈窗 specificity 修復**：修正 `.user-popover` 之 CSS 優先權衝突，確保 `.active` 狀態能正確觸發顯示。
- **組件結構補完**：於 `popover.html` 補齊頭像顯示元素，增強使用者識別度。

### 2026-04-03 實體化接管與 GitHub 監控增強錄
1. **GitHub 即時監控實裝**：
   - 串接 /api/system_status 回傳 /repos/deven951130/Absolute-Axis 即時數據。
   - 前端 5s 輪詢機制與 Pulse 脈搏動畫同步。
2. **NAS 管理中樞實體化 (Bare-Metal Realization)**：
   - 移除 Crucial/WD RED 模擬 Occupants，改為 ST6000DM003 (6TB) 實體數據。
   - 新增 /api/system/hardware 實體硬件掃描接口，整合 smartctl 報告。
   - 重構 RAID 區域為實體儲存池 (Physical Storage Pool)，支援 JBOD 邏輯監控。
3. **系統架構優化**：
   - 建立 axis.service 自動化啟動守護進程，確保後端穩定。
   - 完成 sudoers 特權配置，支援非 root 調用硬體 S.M.A.R.T 指令。

## [2026-04-01] - 實體數據接軌與架構優化
### **核心更新 (Major Architecture Refactor)**
- **實體硬體監控對接 (Hardware Integrity)**：
    - 移除 `system.py` 中所有的 `random` 模擬隨機值。
    - **頻寬真實化**：實作 `NET_STATE` 緩存機制，精確計算物理網卡 MB/s 流量差值。
    - **溫度實例化**：對接 Linux `coretemp` 接口，提供實體與擬合雙重熱能採集。
    - **OS/GPU 動態識別**：基於系統核心路徑，自動回傳真實的伺服器發行版資訊。
- **前端模組化架構精簡**：
    - 完成 `index.html` 徹底拆解，轉向併發式 `app.js` 動態組件加載。

### **機能修正 (Fixes & Aesthetics)**
- **彈窗視覺修復**：修正模組化加載後的視控疊加問題。
- **NAS 選單解鎖**：開通資料夾層級的「直接下載」與「共用」功能，確保權限對位。
- **配色精確命名**：更新品牌配色名為「火花」與「花火」聯名系列。
