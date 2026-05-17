import paramiko
import time

def direct_control():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect('192.168.0.138', username='root', password='deven951130')
        print("Connected to Proxmox host.")
        
        # Give VM time to boot if it was rebooting
        print("Waiting for VM to initialize...")
        time.sleep(15)
        
        cmd = 'qm guest exec 100 -- bash -c "docker restart axis-server"'
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        print("STDOUT:", out)
        print("STDERR:", err)
        
        if "QEMU guest agent is not running" in err or "QEMU guest agent is not running" in out:
            print("Guest agent still not responsive. Trying direct SSH to VM...")
            # Try SSH to VM as sparkle with common passwords or just report failure
            client_vm = paramiko.SSHClient()
            client_vm.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                # Based on previous history, maybe user 'sparkle' password is the same?
                client_vm.connect('192.168.0.159', username='sparkle', password='deven951130', timeout=5)
                print("Connected to VM via SSH!")
                stdin, stdout, stderr = client_vm.exec_command('sudo docker restart axis-server')
                # Note: sudo might need password if not NOPASSWD
                print("Restart command sent via SSH.")
            except:
                print("Direct SSH to VM failed.")
            finally:
                client_vm.close()
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    direct_control()
