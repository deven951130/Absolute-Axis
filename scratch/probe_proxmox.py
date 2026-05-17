import paramiko

def probe_proxmox():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.138', username='root', password='deven951130', timeout=10)
        
        print("Checking storage...")
        stdin, stdout, stderr = client.exec_command('pvesm status')
        print(stdout.read().decode())
        
        print("Checking templates...")
        stdin, stdout, stderr = client.exec_command('pveam available')
        out = stdout.read().decode()
        # Just find ubuntu templates
        ubuntu_tmpl = [line for line in out.split('\\n') if 'ubuntu' in line]
        print("\\n".join(ubuntu_tmpl[:5]))
        
        print("Checking existing VMs...")
        stdin, stdout, stderr = client.exec_command('qm list && pct list')
        print(stdout.read().decode())
        
        print("Checking downloaded templates...")
        stdin, stdout, stderr = client.exec_command('pvesm list local | grep vztmpl')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    probe_proxmox()
