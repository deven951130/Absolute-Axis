import paramiko

def check_lxc_status():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.138', username='root', password='deven951130', timeout=10)
        
        stdin, stdout, stderr = client.exec_command('pct list')
        print(stdout.read().decode())
        
        # Check IP
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ip -4 addr show eth0 | grep inet")
        print("IP:\n" + stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_lxc_status()
