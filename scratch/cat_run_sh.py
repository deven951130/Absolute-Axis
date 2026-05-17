import paramiko

def cat_run_sh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.159', username='sparkle', password='951130', timeout=10)
        
        stdin, stdout, stderr = client.exec_command('cat /home/sparkle/Absolute-Axis/minecraft-data/run.sh')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    cat_run_sh()
