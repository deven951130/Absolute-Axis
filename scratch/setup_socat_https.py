import paramiko
import time

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Killing existing socat processes on port 443 (if any)...")
pve_client.exec_command("fuser -k 443/tcp")

print("Generating self-signed SSL certificate...")
cert_cmd = (
    "openssl req -new -x509 -days 365 -nodes "
    "-out /tmp/server.crt -keyout /tmp/server.key "
    "-subj '/C=TW/ST=Taiwan/L=Taipei/O=AbsoluteAxis/CN=absoluteaxis.dpdns.org' && "
    "cat /tmp/server.key /tmp/server.crt > /tmp/server.pem"
)
pve_client.exec_command(cert_cmd)
time.sleep(2)

print("Starting socat to forward PVE:443 (HTTPS) to VM:8000 (HTTP)...")
pve_client.exec_command("nohup socat OPENSSL-LISTEN:443,reuseaddr,cert=/tmp/server.pem,verify=0,fork TCP4:192.168.0.159:8000 > /dev/null 2>&1 &")

print("Checking if socat on 443 is running...")
stdin, stdout, stderr = pve_client.exec_command("ss -tapn | grep :443")
print(stdout.read().decode())

pve_client.close()
