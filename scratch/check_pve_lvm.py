import paramiko

def check_pve_lvm():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("=== LVM Volume Groups (vgs) ===")
        stdin, stdout, stderr = client.exec_command("vgs")
        print(stdout.read().decode())
        
        print("=== LVM Logical Volumes (lvs) ===")
        stdin, stdout, stderr = client.exec_command("lvs")
        print(stdout.read().decode())
        
        print("=== Size of simplebackups inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- du -sh /root/minecraft/simplebackups")
        print(stdout.read().decode())
        
        print("=== Total size of minecraft folder inside LXC 102 ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- du -sh /root/minecraft")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_pve_lvm()
