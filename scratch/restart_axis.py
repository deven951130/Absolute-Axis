import paramiko

def restart_server():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ip = '192.168.0.138'
    user = 'root'
    password = 'deven951130'
    try:
        print(f"Connecting to {ip}...")
        client.connect(ip, username=user, password=password, timeout=10)
        print("Restarting docker container axis-server inside VM 100...")
        stdin, stdout, stderr = client.exec_command('qm guest exec 100 -- bash -c "docker restart axis-server"')
        print(stdout.read().decode())
        print(stderr.read().decode())
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    restart_server()
