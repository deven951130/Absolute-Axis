import paramiko
import time

def start_lxc_check():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    print(f"Connecting to PVE host at {pve_ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("\n[*] Starting LXC 102 (pct start 102)...")
        stdin, stdout, stderr = client.exec_command("pct start 102")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("Waiting 10 seconds for LXC 102 to boot...")
        time.sleep(10)
        
        print("\n=== LXC 102 Status ===")
        stdin, stdout, stderr = client.exec_command("pct list | grep 102")
        print(stdout.read().decode())
        
        print("\n=== Files in LXC 102's /root ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root")
        print(stdout.read().decode())
        
        print("\n=== Files in LXC 102's /root/minecraft ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root/minecraft")
        print(stdout.read().decode())
        
        print("\n=== Crontab inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- crontab -l")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("\n=== Systemd Minecraft service status inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("\n=== Find backups inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- find / -name '*backup*' -o -name '*Backup*' 2>/dev/null | head -n 50")
        print(stdout.read().decode())
        
        print("\n=== Connect to VM 100 from PVE and list minecraft-data ===")
        cmd_vm = "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa sparkle@192.168.0.159 'ls -la /home/sparkle/Absolute-Axis/minecraft-data'"
        stdin, stdout, stderr = client.exec_command(cmd_vm)
        print(stdout.read().decode())
        print(stderr.read().decode())

        print("\n=== Find backups in VM 100 ===")
        cmd_vm_backup = "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa sparkle@192.168.0.159 'find /home/sparkle/ -name \"*backup*\" -o -name \"*Backup*\" 2>/dev/null | head -n 50'"
        stdin, stdout, stderr = client.exec_command(cmd_vm_backup)
        print(stdout.read().decode())
        print(stderr.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    start_lxc_check()
