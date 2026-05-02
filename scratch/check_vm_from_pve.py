import paramiko

def run_pve_cmd(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    client.close()
    return out, err

print("--- Checking sshpass ---")
out, err = run_pve_cmd("which sshpass")
print(out if out else "Not found")

print("\n--- Checking VM connectivity from Proxmox ---")
out, err = run_pve_cmd("ping -c 3 192.168.0.159")
print(out)
if err: print("ERR:", err)
