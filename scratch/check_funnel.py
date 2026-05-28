import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking Tailscale status...")
stdin, stdout, stderr = pve_client.exec_command("tailscale status")
print(stdout.read().decode())

print("Trying to enable Tailscale Funnel on port 80...")
stdin, stdout, stderr = pve_client.exec_command("tailscale funnel 80")
out = stdout.read().decode()
err = stderr.read().decode()
print("STDOUT:", out)
print("STDERR:", err)

pve_client.close()
