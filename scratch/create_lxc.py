import paramiko
import time

def setup_lxc():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to Proxmox...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        
        print("Downloading Ubuntu 22.04 template (might take a minute)...")
        stdin, stdout, stderr = client.exec_command('pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.zst')
        exit_status = stdout.channel.recv_exit_status()
        print(stdout.read().decode())
        
        print("Creating LXC Container 102 (10GB RAM, 8 Threads)...")
        # Ensure 102 doesn't exist already or destroy it
        client.exec_command('pct stop 102; pct destroy 102')
        time.sleep(2)
        
        cmd_create = "pct create 102 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst -storage local-lvm -cores 8 -memory 10240 -net0 name=eth0,bridge=vmbr0,ip=dhcp -hostname axis-mc-lxc --features nesting=1 -password 951130 -unprivileged 0"
        stdin, stdout, stderr = client.exec_command(cmd_create)
        exit_status = stdout.channel.recv_exit_status()
        print(stdout.read().decode())
        
        print("Starting LXC 102...")
        client.exec_command('pct start 102')
        time.sleep(10)
        
        print("Enabling SSH Root Login...")
        client.exec_command("pct exec 102 -- sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config")
        client.exec_command("pct exec 102 -- systemctl restart ssh")
        
        print("Getting IP Address...")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'")
        lxc_ip = stdout.read().decode().strip()
        print(f"LXC IP Address: {lxc_ip}")
        
        if not lxc_ip:
            print("Failed to get IP address. Waiting 10s and retrying...")
            time.sleep(10)
            stdin, stdout, stderr = client.exec_command("pct exec 102 -- ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'")
            lxc_ip = stdout.read().decode().strip()
            print(f"LXC IP Address: {lxc_ip}")
            
        print("Installing Java 17 and Unzip inside LXC...")
        install_cmd = "pct exec 102 -- bash -c 'apt-get update && apt-get install -y openjdk-17-jre-headless unzip screen'"
        stdin, stdout, stderr = client.exec_command(install_cmd)
        exit_status = stdout.channel.recv_exit_status()
        print("Installation complete.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    setup_lxc()
