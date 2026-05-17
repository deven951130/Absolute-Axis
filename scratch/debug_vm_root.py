import paramiko

def debug_vm_root():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=10)
        print("Checking where the actual code is running...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker inspect axis-server --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"')
        print(stdout.read().decode())
        
        print("\nChecking currently used dashboard.html content on disk...")
        # 我們直接對掛載源進行 grep
        stdin, stdout, stderr = client.exec_command('grep "mc-config" /home/sparkle/absolute-axis/static/components/views/dashboard.html')
        print(f"Grep result: {stdout.read().decode()}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    debug_vm_root()
