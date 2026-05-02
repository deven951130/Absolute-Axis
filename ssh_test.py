import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('100.124.203.61', username='root', password='deven951130', timeout=5)
cmd = "qm guest exec 100 -- bash -c 'docker ps'"
stdin, stdout, stderr = client.exec_command(cmd)
print('STDOUT:\n' + stdout.read().decode())
print('STDERR:\n' + stderr.read().decode())
client.close()
