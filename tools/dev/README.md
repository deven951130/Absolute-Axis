# 本機檢視介面（開發用）

不連真的 DeviceHub／Proxmox，在自己的電腦上看 Axis 的畫面。

```
python tools/dev/fake_devicehub.py      # 假的 DeviceHub integration API，127.0.0.1:18080
python tools/dev/run_axis_local.py      # 本機 Axis，127.0.0.1:18000（另開一個終端機）
python tools/dev/run_axis_local.py --bare   # 模擬全新自架：連 DeviceHub 都不接，所有選用整合顯示「未設定」
```

- `run_axis_local.py` 用暫存資料夾當 `AXIS_BASE_PATH`（資料庫、日誌不會寫進 repo），`static/` 以目錄連結（Windows `mklink /J`）指回 repo，改前端檔案重新整理就看得到。
- JWT 密鑰與管理員密碼每次隨機產生、不顯示；會產生一個本機測試用的登入 token 到 `tools/dev/axis-local-token.txt`（已被 .gitignore 排除）。
  在瀏覽器開 `http://127.0.0.1:18000/main`，於開發者主控台執行：
  `localStorage.setItem('axis_token', '<token>'); localStorage.setItem('axis_role', 'Administrator'); localStorage.setItem('axis_user', 'admin'); location.reload()`
- 本機沒有 Docker，容器相關 API 會回 500（右下角的「伺服器錯誤」提示是正常的）；沒設定 Proxmox 時虛擬化中心顯示「尚未連接 Proxmox」。
  虛擬化中心要看畫面時，可在主控台暫時把 `window.authFetch` 換成回傳假資料的版本。
- 需要的套件：`requirements.txt` ＋ `uvicorn`。
