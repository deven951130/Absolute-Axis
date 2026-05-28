import paramiko
import time
import sys

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
except Exception as e:
    print(f"FAILED to connect to PVE: {e}")
    sys.exit(1)

print("Background HTML monitor started...")
max_attempts = 120 # 10 分鐘
attempt = 0
success = False

while attempt < max_attempts:
    stdin, stdout, stderr = pve_client.exec_command("curl -s http://192.168.0.159:8000/")
    html = stdout.read().decode('utf-8')
    
    if "pricing" in html or "定價" in html:
        print("\n[SUCCESS] 偵測到服務已更新至最新 V43 版本！")
        success = True
        break
        
    attempt += 1
    sys.stdout.write(f"\r監測中... ({attempt}/{max_attempts}) - 仍為舊版伺服器")
    sys.stdout.flush()
    time.sleep(5)

if not success:
    print("\n[TIMEOUT] 監測超時。")

pve_client.close()
