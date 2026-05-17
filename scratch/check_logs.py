import paramiko

def check_logs_v2():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130')
        print("Checking docker ps...")
        # Using -S for password
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker ps')
        print("PS STDOUT:", stdout.read().decode())
        print("PS STDERR:", stderr.read().decode())
        
        print("\nChecking docker logs for axis-server...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker logs axis-server --tail 20')
        print("LOGS STDOUT:", stdout.read().decode())
        print("LOGS STDERR:", stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_logs_v2()
