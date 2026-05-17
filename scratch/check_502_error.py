import paramiko

def check_container_logs():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=10)
        print("Checking container status...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker ps -a | grep axis-server')
        print(stdout.read().decode())
        
        print("\nChecking container logs for errors...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker logs --tail 50 axis-server')
        print(stdout.read().decode())
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_container_logs()
