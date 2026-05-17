import paramiko

def fix_with_docker_compose_v2():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=20)
        print("Using docker compose (V2) to restart services...")
        # 注意：Ubuntu 現代版本通常使用 'docker compose' 而非 'docker-compose'
        cmd = 'cd /home/sparkle/Absolute-Axis && echo "951130" | sudo -S docker compose up -d'
        stdin, stdout, stderr = client.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Verifying if containers are UP...")
        import time
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker ps')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_with_docker_compose_v2()
