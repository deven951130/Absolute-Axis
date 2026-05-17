import paramiko

def manual_unzip():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130', timeout=10)
        
        # Unzip
        print("Unzipping...")
        stdin, stdout, stderr = client.exec_command('cd /home/sparkle/Absolute-Axis/minecraft-data && unzip -q -o server.zip')
        
        # Wait for command to finish
        exit_status = stdout.channel.recv_exit_status()
        
        print("STDOUT:\n", stdout.read().decode(errors='ignore')[:1000])
        print("STDERR:\n", stderr.read().decode(errors='ignore')[:1000])
        print("Exit status:", exit_status)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    manual_unzip()
