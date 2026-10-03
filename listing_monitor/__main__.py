"""Usage: python -m listing_monitor config.json [--once]"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time

from .filters import Query
from .sources import SourceBlocked, build_source
from .store import SeenStore
from .telegram import TelegramNotifier

log = logging.getLogger("listing_monitor")


def check_once(sources, queries: list[Query], store: SeenStore, notifier: TelegramNotifier | None) -> int:
    sent = 0
    for source in sources:
        for query in queries:
            if not query.wants(source.name):
                continue
            try:
                found = source.search(query.text)
            except SourceBlocked as exc:
                log.warning("%s — skipping until checked manually", exc)
                continue
            except Exception as exc:  # one broken site should not stop the others
                log.warning("%s / %r failed: %r", source.name, query.text, exc)
                continue

            matching = [item for item in found if query.matches(item)]
            first_run = not store.has_history(source.name, query.text)
            new = store.add_new(source.name, query.text, matching)
            log.info("%s / %r: %d found, %d match, %d new", source.name, query.text,
                     len(found), len(matching), len(new))
            # On the first run we only remember what is already listed, otherwise
            # the chat gets flooded with old items.
            if first_run or notifier is None:
                continue
            for item in new:
                notifier.send(item, query.text)
                sent += 1
                time.sleep(0.5)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(prog="listing_monitor")
    parser.add_argument("config")
    parser.add_argument("--once", action="store_true", help="run a single check (for cron)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    sources = [build_source(s) for s in config["sources"]]
    queries = [Query(**q) for q in config["queries"]]
    store = SeenStore(config.get("db", "seen.sqlite"))

    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    notifier = TelegramNotifier(token, chat_id) if token and chat_id else None
    if notifier is None:
        log.warning("TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not set, new listings go to the log only")

    while True:
        sent = check_once(sources, queries, store, notifier)
        log.info("check finished, %d sent", sent)
        if args.once:
            break
        time.sleep(60 * config.get("interval_minutes", 10))


if __name__ == "__main__":
    main()
