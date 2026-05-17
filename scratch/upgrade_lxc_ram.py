import paramiko

def upgrade_lxc_ram():
    px_ip = '192.168.0.138'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(px_ip, username='root', password='deven951130', timeout=10)
        
        print("Upgrading LXC 102 RAM to 16G...")
        client.exec_command('pct set 102 -memory 16384')
        
        print("Updating user_jvm_args.txt to 14G inside LXC...")
        # 預留 2G 給系統，讓 JVM 用 14G
        cmd = 'echo "-Xmx14G" > /root/minecraft/user_jvm_args.txt && echo "-Xms14G" >> /root/minecraft/user_jvm_args.txt'
        client.exec_command(f'pct exec 102 -- bash -c \'{cmd}\'')
        
        print("Restarting Minecraft screen...")
        # 殺掉舊的 Java
        client.exec_command('pct exec 102 -- pkill -9 java')
        # 重新啟動
        client.exec_command('pct exec 102 -- bash -c "cd /root/minecraft && screen -dmS mc bash run.sh"')
        
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    upgrade_lxc_ram()
