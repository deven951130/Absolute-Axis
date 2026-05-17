import paramiko

def resize_lxc_disk():
    px_ip = '192.168.0.138'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to Proxmox...")
        client.connect(px_ip, username='root', password='deven951130', timeout=10)
        
        print("Resizing LXC 102 rootfs by +10G...")
        stdin, stdout, stderr = client.exec_command('pct resize 102 rootfs +10G')
        print("Stdout:", stdout.read().decode())
        print("Stderr:", stderr.read().decode())
        
        print("Checking new disk space in LXC...")
        stdin, stdout, stderr = client.exec_command('pct exec 102 -- df -h /')
        print(stdout.read().decode())
        
        print("Cleaning up partial files...")
        client.exec_command('pct exec 102 -- rm -f /root/minecraft/server.zip /root/server.zip')

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    resize_lxc_disk()
