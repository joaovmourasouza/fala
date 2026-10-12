import argparse
import sys

from . import config, ipc

COMMANDS = {
    "run": "inicia o app (padrão)",
    "toggle": "começa ou para de ditar",
    "start": "começa a ditar",
    "stop": "para e insere o texto",
    "cancel": "descarta a gravação atual",
    "quit": "encerra o app",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fala",
        description="Ditado por voz em qualquer app.",
        epilog="\n".join(f"  {k:<8} {v}" for k, v in COMMANDS.items()),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="run", choices=COMMANDS, metavar="comando")
    args = parser.parse_args()

    if args.command != "run":
        if not ipc.send(args.command):
            sys.exit("fala não está rodando. Inicie com: fala")
        return

    if ipc.send("ping"):
        sys.exit("fala já está rodando.")
    from .app import run

    sys.exit(run(config.load()))


if __name__ == "__main__":
    main()
