import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking for docker on PVE...")
stdin, stdout, stderr = pve_client.exec_command("docker --version")
out = stdout.read().decode().strip()
print("Docker:", out)

if out:
    print("Docker is installed on PVE! We can deploy directly here if needed.")
else:
    print("Docker is not installed on PVE.")

pve_client.close()
