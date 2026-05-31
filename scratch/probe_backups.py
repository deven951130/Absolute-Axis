import paramiko

def probe_lxc_backups():
    lxc_ip = "192.168.0.130"
    lxc_user = "root"
    lxc_pass = "951130"
    
    print(f"Connecting to LXC container at {lxc_ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username=lxc_user, password=lxc_pass, timeout=10)
        
        print("\n=== Directory listing of /root ===")
        stdin, stdout, stderr = client.exec_command("ls -la /root")
        print(stdout.read().decode())
        
        print("\n=== Directory listing of /root/minecraft ===")
        stdin, stdout, stderr = client.exec_command("ls -la /root/minecraft")
        print(stdout.read().decode())
        
        print("\n=== Crontab list ===")
        stdin, stdout, stderr = client.exec_command("crontab -l")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("\n=== Systemd Services ===")
        stdin, stdout, stderr = client.exec_command("systemctl list-units --type=service --all | grep -i mc")
        print(stdout.read().decode())
        
        print("\n=== Finding any backup files (*.zip, *.tar.gz, backups folder) in /root ===")
        stdin, stdout, stderr = client.exec_command("find /root -name '*backup*' -o -name '*Backup*'; find / -maxdepth 2 -name '*backup*' 2>/dev/null")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    probe_lxc_backups()
