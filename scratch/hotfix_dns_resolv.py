import paramiko

def hotfix_dns():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("[*] Writing nameserver 8.8.8.8 directly to /etc/resolv.conf inside LXC 102...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- bash -c \"echo 'nameserver 8.8.8.8' > /etc/resolv.conf\"")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("[*] Checking /etc/resolv.conf inside LXC 102...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- cat /etc/resolv.conf")
        print(stdout.read().decode())
        
        print("[*] Testing DNS resolution inside LXC 102 (ping google.com)...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ping -c 3 google.com")
        out = stdout.read().decode()
        err = stderr.read().decode()
        print("STDOUT:")
        print(out)
        print("STDERR:")
        print(err)
        
        if "bytes from" in out:
            print("[+] DNS resolution successfully hotfixed!")
        else:
            print("[-] DNS resolution hotfix failed.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    hotfix_dns()
