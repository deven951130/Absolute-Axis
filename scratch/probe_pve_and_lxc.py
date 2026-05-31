import paramiko

def probe_pve_lxc():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    print(f"Connecting to PVE host at {pve_ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("\n=== PVE LXC container list (pct list) ===")
        stdin, stdout, stderr = client.exec_command("pct list")
        print(stdout.read().decode())
        
        print("\n=== PVE VM list (qm list) ===")
        stdin, stdout, stderr = client.exec_command("qm list")
        print(stdout.read().decode())

        print("\n=== LXC 102 configuration (pct config 102) ===")
        stdin, stdout, stderr = client.exec_command("pct config 102")
        print(stdout.read().decode())
        print(stderr.read().decode())

        print("\n=== Checking files in LXC 102's /root/minecraft directory via pct exec ===")
        # Note: we use 'pct exec 102 -- ls -la /root' to run commands directly inside LXC
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root")
        print(stdout.read().decode())
        print(stderr.read().decode())

        print("\n=== Checking LXC 102's minecraft directory ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ls -la /root/minecraft")
        print(stdout.read().decode())
        print(stderr.read().decode())

        print("\n=== Checking crontab inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- crontab -l")
        print(stdout.read().decode())
        print(stderr.read().decode())

        print("\n=== Find any backups in PVE host or LXC 102 ===")
        # Search LXC 102
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- find /root -name '*backup*' -o -name '*Backup*'; pct exec 102 -- find / -maxdepth 2 -name '*backup*' 2>/dev/null")
        print("LXC 102 Backups find result:")
        print(stdout.read().decode())
        
        # Search PVE host
        stdin, stdout, stderr = client.exec_command("find / -maxdepth 3 -name '*minecraft*' -o -name '*backup*' 2>/dev/null | grep -E 'backup|minecraft' | head -n 30")
        print("PVE Host Backups find result:")
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    probe_pve_lxc()
