import paramiko

def check_lxc_ram():
    px_ip = '192.168.0.138'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(px_ip, username='root', password='deven951130', timeout=10)
        print("Checking LXC 102 Config...")
        stdin, stdout, stderr = client.exec_command('pct config 102')
        print(stdout.read().decode())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_lxc_ram()
