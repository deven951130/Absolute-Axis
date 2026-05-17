import paramiko

def check_files():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130', timeout=10)
        
        # Check files
        print("Listing files in minecraft-data...")
        stdin, stdout, stderr = client.exec_command('ls -l /home/sparkle/Absolute-Axis/minecraft-data')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_files()
