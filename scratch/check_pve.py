import paramiko
import sys

def run_pve_cmd(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        client.close()
        return out, err
    except Exception as e:
        return "", str(e)

print("--- PVE VM Status ---")
out, err = run_pve_cmd("qm list")
print(out)
if err: print("ERR:", err)

print("\n--- Network Config on PVE ---")
out, err = run_pve_cmd("ip addr")
print(out)
