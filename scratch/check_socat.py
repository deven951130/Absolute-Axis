import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking for socat...")
stdin, stdout, stderr = pve_client.exec_command("which socat")
out = stdout.read().decode().strip()
print("socat path:", out)

if not out:
    print("Socat not found, trying to install...")
    pve_client.exec_command("apt-get update && apt-get install -y socat")
    stdin, stdout, stderr = pve_client.exec_command("which socat")
    print("socat path after install:", stdout.read().decode().strip())

pve_client.close()
