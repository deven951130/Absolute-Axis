import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking qm guest exec on VM 100...")
stdin, stdout, stderr = pve_client.exec_command("qm guest exec 100 -- bash -c 'whoami'")
print("Out:", stdout.read().decode().strip())
print("Err:", stderr.read().decode().strip())

pve_client.close()
