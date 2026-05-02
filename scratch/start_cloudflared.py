import paramiko

def run_cmd_on_vm(command):
    pve_client = paramiko.SSHClient()
    pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    transport = pve_client.get_transport()
    channel = transport.open_channel("direct-tcpip", (vm_ip, 22), ('100.124.203.61', 22))
    
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vm_client.connect(vm_ip, username=vm_user, password=vm_pass, sock=channel)
    
    stdin, stdout, stderr = vm_client.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    vm_client.close()
    pve_client.close()
    return out, err

print("--- Docker networks on VM ---")
out, err = run_cmd_on_vm("docker network ls")
print(out)

print("\n--- Trying to start cloudflared specifically ---")
out, err = run_cmd_on_vm("cd /home/sparkle/Absolute-Axis && docker compose up -d cloudflared")
print(out)
if err: print("ERR:", err)
