import paramiko

def restart_api():
    vm_ip = '192.168.0.159'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(vm_ip, username='sparkle', password='951130', timeout=10)
        print("Restarting Absolute-Axis container...")
        client.exec_command('echo "951130" | sudo -S docker restart axis-server')
        print("Restarted!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    restart_api()
