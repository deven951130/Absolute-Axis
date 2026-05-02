import paramiko
import time

def run_cmd_on_vm(command):
    # Connect to Proxmox
    pve_client = paramiko.SSHClient()
    pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
    
    # Create a transport to the VM via Proxmox
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    transport = pve_client.get_transport()
    dest_addr = (vm_ip, 22)
    local_addr = ('100.124.203.61', 22) # Not strictly necessary but good practice
    channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)
    
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vm_client.connect(vm_ip, username=vm_user, password=vm_pass, sock=channel)
    
    stdin, stdout, stderr = vm_client.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    vm_client.close()
    pve_client.close()
    return out, err

print("--- Checking Docker containers on VM ---")
out, err = run_cmd_on_vm("docker ps -a")
print(out)
if err: print("ERR:", err)

print("\n--- Checking Cloudflared logs ---")
out, err = run_cmd_on_vm("docker logs axis-cloudflared --tail 20")
print(out)
if err: print("ERR:", err)

print("\n--- Checking .env on VM ---")
# Assume project is in /home/sparkle/Absolute-Axis or similar
out, err = run_cmd_on_vm("ls -R /home/sparkle")
print(out)
