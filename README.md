# 🌐 Absolute-Axis (絕對軸心)

> **「融合私有雲、智慧物聯網與 AI 賦能的次世代居家伺服器樞紐」**

## 📝 專案簡介 (Project Overview)
**Absolute-Axis** 是一個以「資訊安全」、「易維護性」與「極致節能」為三大核心理念，從零打造的現代化智慧家庭與私有雲端中樞系統。

在現代數位生活中，檔案儲存、遊戲伺服器、IoT 智慧家電往往各自獨立，導致管理困難且耗費不必要的電力。本專案透過微服務架構 (Docker) 將所有服務容器化，並自主開發「**總控制介面 (Absolute-Axis)**」，作為掌管硬體資源分配、電源調度、網路安全與環境監測的「**絕對中樞大腦**」。

無論是遠端存取 NAS 檔案、一鍵啟閉遊戲伺服器，還是查看家中實時的溫濕度數據，都能透過 Absolute-Axis 直覺的儀表板一次搞定。

## ✨ 核心特色 (Core Features)

*   🎛️ **全域控制中樞 (Total Control Dashboard)**
    *   專屬的 Web 視覺化儀表板，即時監控伺服器底層狀態（CPU、記憶體、硬碟使用率）。
    *   透過 Docker API 深度整合，讓使用者能在圖形介面上一鍵啟動 / 關閉特定的服務（如 Minecraft/Palworld 遊戲伺服器、私有雲），實現微操等級的環境管理。
*   ☁️ **高隱私私有雲 (Private NAS & Storage)**
    *   整合 Nextcloud 等開源方案，建立完全屬於自己的雲端硬碟，自主掌握資料主權，擺脫公有雲的容量限制與隱私疑慮。
*   🏠 **AIoT 智慧家庭聯控**
    *   硬體端串接 ESP32/Raspberry Pi 等微控制器與環境感測模組。
    *   使用 MQTT 輕量級通訊協定結合 InfluxDB 時序資料庫，完美收集並視覺化居家環境數據，為未來的自定義自動化腳本鋪路。
*   🛡️ **軍規級資訊安全 (Security First)**
    *   嚴格遵守「最小權限原則」，後端與資料庫徹底隱蔽於內網。
    *   全面部署 UFW 防火牆，並整合 WireGuard VPN 進行內網穿透。即便人在外地，也能安全無虞地連線回 Absolute-Axis 進行遠端管理。
*   🤖 **AI 智能隨身助理**
    *   整合大型語言模型 (RAG / API)，賦予中樞系統理解與對話的能力。未來可拓展為能讀取個人私有雲文件並進行精準問答的超級大腦。
*   ⚡ **極限節能與自動化 (Green IT)**
    *   透過腳本自動化管理與進階排程 (Cronjob)，在無人使用耗電服務時自動休眠或關閉特定容器，最大化延長硬體壽命並節省電費支出。

## 🏗️ 系統架構圖 (System Architecture)
*   **底層作業系統**：Ubuntu Server (Headless)
*   **虛擬化技術**：Docker & Docker Compose
*   **核心後端 (大腦)**：Python (FastAPI / Flask) 或 Node.js (實作系統指令與 Docker API 溝通)
*   **前端介面 (雙眼)**：Vue.js / React (實時監控儀表板)
*   **資料流與通訊**：Mosquitto (MQTT), InfluxDB, RESTful API
*   **資安網路**：WireGuard VPN, UFW 防火牆

## 🎯 發展藍圖 (Roadmap)
本專案採用敏捷式開發策略，階段性目標請參閱 [Project Roadmap](./project_roadmap.md)，包含從建立核心 MVP 架構、串接 IoT 裝備，直到最終導入 AI 客服與完善資安防禦網的完整實作路徑。
