import paramiko

def check_lxc_error():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Checking directory contents:")
        stdin, stdout, stderr = client.exec_command('ls -la /root/minecraft')
        print(stdout.read().decode())
        
        print("Trying to run directly to get error message:")
        stdin, stdout, stderr = client.exec_command('cd /root/minecraft && bash run.sh', timeout=10)
        try:
            import time
            time.sleep(5)
            print("STDOUT:", stdout.read().decode())
            print("STDERR:", stderr.read().decode())
        except:
            print("Process is still running.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_lxc_error()
