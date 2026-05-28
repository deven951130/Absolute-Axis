import paramiko

print("Connecting to PVE...")
pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Opening direct-tcpip channel to VM...")
transport = pve_client.get_transport()
# direct-tcpip: (dest_ip, dest_port), (src_ip, src_port)
vm_channel = transport.open_channel("direct-tcpip", ("192.168.0.159", 22), ("127.0.0.1", 0))

print("Connecting to VM via PVE proxy...")
vm_client = paramiko.SSHClient()
vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
vm_client.connect('192.168.0.159', username='sparkle', password='deven951130', sock=vm_channel, timeout=10)

print("SUCCESS! Running test command on VM...")
stdin, stdout, stderr = vm_client.exec_command("whoami && pwd && git status")
print("STDOUT:")
print(stdout.read().decode())
print("STDERR:")
print(stderr.read().decode())

vm_client.close()
pve_client.close()
