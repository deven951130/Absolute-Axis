import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

stdin, stdout, stderr = pve_client.exec_command("curl -k -s https://absoluteaxis.dpdns.org")
output = stdout.read()
try:
    print(output.decode('utf-8'))
except Exception:
    print(output)

pve_client.close()
