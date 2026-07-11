import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.0.138', username='root', password='deven951130', timeout=5)
def run(cmd):
    print(f"Exec: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    print("STDOUT:\n" + stdout.read().decode())
    print("STDERR:\n" + stderr.read().decode())

run("ps aux | grep pct")
run("pct status 102")
client.close()
