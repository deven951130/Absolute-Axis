import paramiko

def configure_proxmox_boot():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ip = '192.168.0.138'
    user = 'root'
    password = 'deven951130'
    
    try:
        print(f"Connecting to {ip}...")
        client.connect(ip, username=user, password=password, timeout=10)
        
        # List VMs to identify the correct one
        print("Fetching VM list...")
        stdin, stdout, stderr = client.exec_command('qm list')
        vms = stdout.read().decode()
        print("VM List:\n" + vms)
        
        # The user's previous script used VM ID 100
        vm_id = '100'
        
        # Set onboot=1
        print(f"Setting VM {vm_id} to start at boot...")
        stdin, stdout, stderr = client.exec_command(f'qm set {vm_id} --onboot 1')
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"Success: {output}")
            
        # Verify the setting
        print(f"Verifying setting for VM {vm_id}...")
        stdin, stdout, stderr = client.exec_command(f'qm config {vm_id} | grep onboot')
        print("Config result: " + stdout.read().decode())
        
    except Exception as e:
        print(f"Failed to connect or execute: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    configure_proxmox_boot()
