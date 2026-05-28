import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking PVE IP routing to VM 100 (192.168.0.159)...")
stdin, stdout, stderr = pve_client.exec_command("ip route get 192.168.0.159")
print("Route:")
print(stdout.read().decode())

print("Checking PVE interfaces...")
stdin, stdout, stderr = pve_client.exec_command("ip addr show")
print("IP Addresses:")
print(stdout.read().decode())

pve_client.close()
