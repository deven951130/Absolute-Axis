import paramiko

def check_mc():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130', timeout=10)
        
        # Check docker logs
        print("Checking docker logs for axis-mc...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker logs --tail 30 axis-mc')
        
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        print("STDOUT:\n", out)
        print("STDERR:\n", err)
        
        # Check process status
        print("Checking CPU usage for Java...")
        stdin, stdout, stderr = client.exec_command('top -b -n 1 | grep java')
        print("TOP:\n", stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_mc()
