import yaml
from network_stack.client.client import Client
from network_stack.client.scan import Scanner


def main() -> None:
    with open('cfg/client_config.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)

    try:
        subnet = config.get("subnet")
    except Exception:
        subnet = None
    try:
        port = config.get("port")
    except Exception:
        port = None
    scanner = Scanner(subnet, port)
    servers = scanner.scan()

    for i, s in enumerate(servers):
        print(f"{i}: {s}")

    selected = False
    ok = True
    ip = ""
    while not selected:
        try:
            inp = input("Select server or q to quit: ")
            if inp == "q" or inp == "Q":
                selected = True
                ok = False
            num = int(inp)
            ip = servers[num]
            selected = True
        except Exception:
            pass

    if ok:
        assert ip, "IP not set"
        assert port, "Port is not set"
        _ = Client(ip, port)


if __name__ == "__main__":
    main()
