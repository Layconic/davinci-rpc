"""Entry point: python -m davinci_rpc [--config PATH] [--verbose]"""

import argparse
import logging
import sys
import time

from . import __version__
from .config import load_config
from .presence import DiscordPresence, PresenceBuilder
from .resolve import ResolveClient

log = logging.getLogger("davinci_rpc")


def main() -> int:
    parser = argparse.ArgumentParser(description="DaVinci Resolve Discord Rich Presence")
    parser.add_argument("--config", help="Pfad zur config.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug-Ausgaben")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config(args.config)
    if not config["client_id"] or not str(config["client_id"]).isdigit():
        log.error("Bitte eine gültige Discord 'client_id' in config.json eintragen "
                  "(siehe README).")
        return 1

    resolve = ResolveClient()
    discord = DiscordPresence(str(config["client_id"]))
    builder = PresenceBuilder(config)

    log.info("DaVinci RPC %s gestartet. Warte auf DaVinci Resolve... (Strg+C zum Beenden)",
             __version__)
    try:
        while True:
            state = resolve.get_state()
            if state.running:
                discord.update(builder.build(state))
            else:
                discord.clear()
                builder.reset()
            time.sleep(config["update_interval"])
    except KeyboardInterrupt:
        log.info("Beende...")
    finally:
        discord.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
