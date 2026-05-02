import paramiko

def run_cmd_on_vm(command):
    pve_client = paramiko.SSHClient()
    pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    transport = pve_client.get_transport()
    channel = transport.open_channel("direct-tcpip", (vm_ip, 22), ('100.124.203.61', 22))
    
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vm_client.connect(vm_ip, username=vm_user, password=vm_pass, sock=channel)
    
    stdin, stdout, stderr = vm_client.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    vm_client.close()
    pve_client.close()
    return out, err

# Using quoted EOF to prevent shell expansion
compose_content = """services:
  axis-server:
    build: .
    container_name: axis-server
    restart: always
    network_mode: host
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - TZ=Asia/Taipei
      - HOST_IP=${HOST_IP:-0.0.0.0}
    volumes:
      - .:/app
      - ./nas:/app/nas
      - /var/run/docker.sock:/var/run/docker.sock
    working_dir: /app
    command: >
      sh -c "pip install -r requirements.txt && 
             uvicorn app.main:app --host $$HOST_IP --port 8000"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: axis-cloudflared
    restart: always
    network_mode: host
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    command: tunnel --no-autoupdate run
"""

print("--- Updating docker-compose.yml on VM (with quoted EOF) ---")
# Note the 'EOF' to prevent expansion
run_cmd_on_vm(f"cat <<'EOF' > /home/sparkle/Absolute-Axis/docker-compose.yml\n{compose_content}\nEOF")

print("--- Restarting all containers ---")
out, err = run_cmd_on_vm("cd /home/sparkle/Absolute-Axis && docker compose up -d --build")
print(out)

print("\n--- Checking logs ---")
time_to_wait = 5
import time
time.sleep(time_to_wait)
out, err = run_cmd_on_vm("docker logs axis-cloudflared --tail 20")
print("Cloudflared logs:\n", out)
