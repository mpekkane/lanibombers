import time
from argparse import ArgumentParser
from network_stack.messages.messages import ChatText
from network_stack.bomber_client import BomberClient


def on_chattxt(msg: ChatText):
    print(msg)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "--cfg", "-c", type=str, default="cfg/client_config.yaml"
    )
    args = parser.parse_args()
    cfg_path = args.cfg

    client = BomberClient(cfg_path)
    server_found = client.find_host()
    if not server_found:
        print("No server found")
        return

    client.set_callback(ChatText, on_chattxt)

    client.start()
    name = input("Name: ")
    client.set_name(name)
    while True:
        msg = input(": ")
        client.send(ChatText(msg))
        time.sleep(0.1)


if __name__ == "__main__":
    main()
