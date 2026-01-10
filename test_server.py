from network_stack.server.server import Server
import yaml


def main() -> None:
    with open('cfg/server_config.yaml', 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)

    port = config.get("port")
    server = Server(port)


if __name__ == "__main__":
    main()
