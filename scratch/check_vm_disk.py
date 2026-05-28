import paramiko

pve_client = paramiko.SSHClient()
pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)

print("Checking VM 100 disk type and guestfs...")
stdin, stdout, stderr = pve_client.exec_command("qm config 100 | grep -i 'scsi\\|ide\\|sata\\|virtio'")
print("Disks:\n", stdout.read().decode().strip())

stdin, stdout, stderr = pve_client.exec_command("which guestmount")
print("guestmount:\n", stdout.read().decode().strip())

pve_client.close()
