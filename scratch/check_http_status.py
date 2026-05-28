import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking if Absolute Axis API is responding on VM IP (192.168.0.159:8000)...")
stdin, stdout, stderr = pve_client.exec_command("curl -I -s --connect-timeout 2 http://192.168.0.159:8000/")
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()

if out:
    print("HTTP Response headers:")
    print(out)
else:
    print("No response from VM 8000 port.")
    if err:
        print("Error details:", err)

pve_client.close()
