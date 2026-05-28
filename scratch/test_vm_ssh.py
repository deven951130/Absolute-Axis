import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

def run_vm_cmd(cmd):
    # 轉義單引號
    escaped_cmd = cmd.replace("'", "'\\''")
    pve_cmd = f"qm guest exec 100 -- bash -c '{escaped_cmd}'"
    print(f"Running PVE Command: {pve_cmd}")
    stdin, stdout, stderr = client.exec_command(pve_cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    print("STDOUT:")
    print(out)
    if err:
        print("STDERR:")
        print(err)
    return out

run_vm_cmd("whoami")
run_vm_cmd("su - sparkle -c 'whoami'")
run_vm_cmd("su - sparkle -c 'cd ~/Absolute-Axis && git status'")
client.close()
