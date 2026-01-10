from network_stack.client.client import Client
from network_stack.client.scan import Scanner

def main() -> None:
    scan = True
    if not scan:
        client = Client("192.168.101.119", 8123)
    else:
        subnet = 101
        port = 8123
        scanner = Scanner(subnet, port)
        servers = scanner.scan()

        for i, s in enumerate(servers):
            print(f"{i}: {s}")

        selected = False
        ok = True
        while not selected:
            try:
                inp = input("Select server or q to quit: ")
                if inp == "q" or inp == "Q":
                    selected = True
                    ok = False
                num = int(inp)
                ip = servers[num]
                selected = True
            except:
                pass

        if ok:
            client = Client(ip, port)


if __name__ == "__main__":
    main()
