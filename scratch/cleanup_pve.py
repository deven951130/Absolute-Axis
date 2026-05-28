import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Cleaning up HTTP server and directory on PVE...")
pve_client.exec_command("kill -9 37496")
pve_client.exec_command("fuser -k 8080/tcp")
pve_client.exec_command("rm -rf /tmp/pve_pub")
print("Done.")

pve_client.close()
