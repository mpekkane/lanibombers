
import time
from argparse import ArgumentParser
from network_stack.bomber_server import BomberServer, ClientContext
from network_stack.messages.messages import Name, ChatText


def on_name(msg: Name, ctx: ClientContext) -> None:
    ctx.name = msg.name
    print("set name:", msg.name)


def on_chat(msg: ChatText, ctx: ClientContext) -> None:
    sender = ctx.name or "?"
    ctx.broadcast(ChatText(text=f"<{sender}> {msg.text}"), exclude_self=True)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--cfg", "-c", type=str, default="cfg/server_config.yaml")
    args = parser.parse_args()
    cfg = args.cfg

    server = BomberServer(cfg)

    server.set_callback(Name, on_name)
    server.set_callback(ChatText, on_chat)

    server.start()

    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    main()
