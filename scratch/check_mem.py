import paramiko

def check_memory():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130', timeout=10)
        
        print("Checking memory...")
        stdin, stdout, stderr = client.exec_command('free -m')
        print(stdout.read().decode())
        
        print("Checking docker ps...")
        stdin, stdout, stderr = client.exec_command('echo "951130" | sudo -S docker ps')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_memory()
