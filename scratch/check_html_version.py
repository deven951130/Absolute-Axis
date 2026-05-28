import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Fetching main page HTML from VM...")
# 執行 GET 請求，取得 HTML 並尋找 pricing 關鍵字
stdin, stdout, stderr = pve_client.exec_command("curl -s http://192.168.0.159:8000/")
html = stdout.read().decode('utf-8')

if "pricing" in html or "定價" in html:
    print("SUCCESS: Found 'pricing' or '定價' in HTML. The server is running the LATEST V43 code!")
else:
    print("WARNING: 'pricing' / '定價' not found in HTML. The server is likely running OLD code.")
    print("HTML Preview (first 1000 chars):")
    print(html[:1000])

pve_client.close()
