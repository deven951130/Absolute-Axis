import paramiko

def force_restart_all():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=20)
        print("Cleaning up zombie containers...")
        client.exec_command('echo "951130" | sudo -S docker stop axis-server axis-cloudflared')
        client.exec_command('echo "951130" | sudo -S docker rm axis-server axis-cloudflared')
        
        print("Starting containers from scratch...")
        stdin, stdout, stderr = client.exec_command('cd /home/sparkle/Absolute-Axis && echo "951130" | sudo -S docker-compose up -d')
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Verifying status...")
        import time
        time.sleep(10)
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker ps')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    force_restart_all()
