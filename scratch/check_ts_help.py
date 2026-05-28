import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

stdin, stdout, stderr = pve_client.exec_command("tailscale funnel --help")
print("Funnel Help:", stdout.read().decode())
print("Funnel Err:", stderr.read().decode())

stdin, stdout, stderr = pve_client.exec_command("tailscale version")
print("TS Version:", stdout.read().decode())

pve_client.close()
