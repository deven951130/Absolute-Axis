import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking PVE Firewall status...")
stdin, stdout, stderr = pve_client.exec_command("pve-firewall status")
print(stdout.read().decode())

print("Checking current connections on port 8080...")
stdin, stdout, stderr = pve_client.exec_command("ss -tapn | grep 8080")
print(stdout.read().decode())

print("Checking if sparkle SSH key works now (manual check)...")
stdin, stdout, stderr = pve_client.exec_command("ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -i /root/.ssh/id_rsa sparkle@192.168.0.159 'whoami'")
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print("Result:", out)
if err:
    print("Stderr:", err)

pve_client.close()
