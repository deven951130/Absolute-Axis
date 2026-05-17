import paramiko

def diagnose_vm_state():
    VM_IP = '192.168.0.159'
    VM_USER = 'sparkle'
    VM_PASS = '951130'
    REPO_PATH = '/home/sparkle/Absolute-Axis'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"[*] 連線至 VM ({VM_IP})...")
        client.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
        print("[+] 連線成功\n")

        checks = [
            ("VM 上最新 git commit",          f"cd {REPO_PATH} && git log --oneline -3"),
            ("index.html 含 multiverse 行數",  f"grep -n 'multiverse' {REPO_PATH}/static/index.html"),
            ("multiverse.html 是否存在",        f"ls -lh {REPO_PATH}/static/components/views/multiverse.html 2>&1"),
            ("multiverse.js 是否存在",          f"ls -lh {REPO_PATH}/static/js/multiverse.js 2>&1"),
            ("minecraft.py 是否存在",           f"ls -lh {REPO_PATH}/app/routers/minecraft.py 2>&1"),
            ("axis-server 容器狀態",            'docker ps --filter "name=axis-server" --format "{{.Names}} | {{.Status}} | {{.Ports}}"'),
            ("容器內 index.html multiverse",    'docker exec axis-server grep -n multiverse /app/static/index.html 2>&1'),
        ]
        
        for label, cmd in checks:
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            result = out or err or "(無輸出)"
            print(f"[{label}]\n    {result}\n")
            
    except Exception as e:
        print(f"[-] 錯誤: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    diagnose_vm_state()
