# 伺服器建置指令完全備忘錄 (CLI Cheat Sheet)

這是一份記錄了我們在「AIoT 絕對軸心戰情室」建置過程中，所有使用過的 Linux 神級指令。未來不管您是要架設新伺服器、轉移專案或排解故障，這份手冊都能幫助您快速回憶。

## 🌐 網路與連線設定 (Network & SSH)
*   **`sudo ip link set enp0s8 up`**
    *   **功用**：喚醒指定的虛擬網卡（這裡的 enp0s8 是 VirtualBox 專屬的網路介面卡）。
*   **`sudo ip addr add 192.168.56.99/24 dev enp0s8`**
    *   **功用**：臨時（重開機就會不見）指派一組內部網路 IP 給網卡，用來突破網管限制。
*   **`sudo netplan apply`**
    *   **功用**：套用我們寫好的永久網路設定檔 (`/etc/netplan/01-enp0s8.yaml`)。
*   **`ssh 帳號@目標機器IP`**（Windows/Mac 適用）
    *   例如：`ssh sparkle@192.168.56.99`
    *   **功用**：從 Windows 的命令提示字元「遠端登入」並完全控制 Linux 虛擬機的操作畫面。
*   **`scp "本機檔案路徑" 帳號@目標IP:目標資料夾`**（Windows/Mac 適用）
    *   例如：`scp "e:\index.html" sparkle@192.168.56.99:~/aiot-master/index.html`
    *   **功用**：「隔空傳檔」，將 Windows 上的網頁直接傳送到虛擬機內。

## 💻 基礎操作與程式開發 (Basic & Python)
*   **`cd ~/aiot-master`**
    *   **功用**：切換目錄 (`Change Directory`)，`~` 代表登入帳號的家目錄（也就是 `/home/sparkle`）。
*   **`ls -la 目錄路徑`**
    *   **功用**：「照妖鏡」，列出資料夾內的所有檔案，包含隱藏檔 (字首為`.`)、擁有者權限與精確位元組大小。
*   **`nano 檔案名稱`**
    *   例如：`nano main.py`
    *   **功用**：在沒有滑鼠的黑視窗環境中，叫出最輕巧好用的文字編輯器。
    *   **操作**：存檔按 `Ctrl+O`，離開按 `Ctrl+X`。
*   **`python3 -m venv venv`**
    *   **功用**：建立乾淨的 Python 虛擬環境（沙盒），讓套件安裝不會弄髒作業系統本身。
*   **`source venv/bin/activate`**
    *   **功用**：啟動 (切換進入) Python 虛擬環境。
*   **`uvicorn main:app --host 0.0.0.0 --port 8000`**
    *   **功用**：以前景模式手動運行 FastAPI 伺服器，`0.0.0.0` 代表允許任何外部電腦透過網路連入。

## 🛡️ 守護程式服務管理 (Systemd)
這是現代 Linux 管理背景伺服器的核心機制。
*   **`systemctl list-unit-files --state=enabled`**
    *   **功用**：掃描並列出系統內所有註冊為「開機自動啟動」的守護程式名單，幫助您揪出躲藏在系統深處的流氓背景開機服務。
*   **`sudo systemctl disable 服務名稱.service`**
    *   **功用**：永久廢除該服務的「開機自動無痛啟動」權限，將流氓程式徹底拔除保命符。
*   **`sudo systemctl daemon-reload`**
    *   **功用**：當我們更動過 `/etc/systemd/...` 的設定檔後，強制系統重讀設定。
*   **`sudo systemctl enable 服務名稱.service`**
    *   **功用**：將這支程式註冊為「開機自動無痛啟動」。
*   **`sudo systemctl start 服務名稱.service`**
    *   **功用**：立刻啟動這個背景伺服器。
*   **`sudo systemctl restart 服務名稱.service`**
    *   **功用**：強制重啟伺服器（當我們修改過 Python 程式碼後，一定要執行這行來重刷伺服器大腦）。
*   **`sudo systemctl status 服務名稱.service`**
    *   **功用**：查看伺服器是不是綠色的 `active (running)`，或者是有沒有發生紅色閃退。

## 🕵️‍♂️ 終極除錯與故障排除 (Advanced Debugging)
工程師抓漏專用的必殺技。
*   **`sudo journalctl -u 服務名稱.service -n 20 --no-pager`**
    *   **功用**：調閱這支背景程式出錯前的「黑盒子紀錄」，印出最後 20 行，用來抓出像 Python 縮排錯誤或 Crash 原因。
*   **`sudo ss -tulpn | grep :8000`**
    *   **功用**：網路雷達掃描，查出目前到底是「哪一隻程式」、「PID 是多少」正在偷偷霸佔著 8000 連接埠。
*   **`sudo fuser -k 8000/tcp`**
    *   **功用**：神擋殺神的必殺技，無差別消滅、砍死所有正在使用 Port 8000 的程式（用來清除殭屍程式超級好用）。
