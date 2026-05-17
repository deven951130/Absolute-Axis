import socket

def test_conn():
    target = ("192.168.0.108", 25565)
    print(f"Testing connection from Windows to {target}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        res = s.connect_ex(target)
        if res == 0:
            print("SUCCESS: Port is open and reachable from Windows.")
        else:
            print(f"FAILED: Connection error code {res}. (10061=Refused, 10060=Timeout)")

if __name__ == "__main__":
    test_conn()
