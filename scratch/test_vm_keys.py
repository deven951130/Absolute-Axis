import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Listing keys in PVE root .ssh directory...")
stdin, stdout, stderr = pve_client.exec_command("ls -la /root/.ssh/")
print("STDOUT:")
print(stdout.read().decode())

print("Testing SSH from PVE to VM 100 using PVE root private keys (if any)...")
# 嘗試用 ssh -i 指向金鑰來登入
stdin, stdout, stderr = pve_client.exec_command("ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa root@192.168.0.159 'whoami'")
print("root with id_rsa:")
print(stdout.read().decode())
print(stderr.read().decode())

stdin, stdout, stderr = pve_client.exec_command("ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa sparkle@192.168.0.159 'whoami'")
print("sparkle with id_rsa:")
print(stdout.read().decode())
print(stderr.read().decode())

# 測試 proxy ssh 到 root
print("Testing root proxy SSH...")
try:
    transport = pve_client.get_transport()
    vm_channel = transport.open_channel("direct-tcpip", ("192.168.0.159", 22), ("127.0.0.1", 0))
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vm_client.connect('192.168.0.159', username='root', password='deven951130', sock=vm_channel, timeout=10)
    print("SUCCESS: Logged in as root via Proxy SSH!")
    stdin, stdout, stderr = vm_client.exec_command("whoami")
    print(stdout.read().decode())
    vm_client.close()
except Exception as e:
    print(f"FAILED root proxy SSH: {e}")

pve_client.close()
