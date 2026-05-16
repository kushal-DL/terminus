"""Entry point for dev console: python -m terminus.dev [--server URL]"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Terminus Dev Console")
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="Server URL")
    args = parser.parse_args()

    from terminus.dev.console import DevConsoleApp
    app = DevConsoleApp(server_url=args.server)
    app.run()


if __name__ == "__main__":
    main()
