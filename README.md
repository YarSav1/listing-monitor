# listing-monitor

Watches marketplaces for **new** listings that match your keywords and sends them to Telegram.
Useful for collectors, resellers and anyone who refreshes the same search page all day.

![tests](https://github.com/YarSav1/listing-monitor/actions/workflows/tests.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## What it does

- Runs your searches every N minutes on several sites at once.
- Filters by required words, stop words and price range.
- Sends only listings it has not seen before — the first run just records the current results,
  so the chat is not flooded with old items.
- One failing site does not stop the others; anti-bot pages are reported, not bypassed.

Supported sources:

| type | how | when to use |
|---|---|---|
| `ebay_api` | official eBay Browse API | eBay — its pages reject scripted requests |
| `css` | plain HTTP + CSS selectors | most search pages |
| `browser` | headless Chromium (Playwright) | pages that need JavaScript to render |

A Telegram message looks like this:

```
Silver coin 1921
12.5 GBP
silver coin · ebay
https://www.ebay.co.uk/itm/...
```

## Quick start

```bash
git clone https://github.com/YarSav1/listing-monitor.git
cd listing-monitor
pip install -e .            # add [browser] for Playwright sources
cp config.example.json config.json
export TELEGRAM_TOKEN=...   # from @BotFather
export TELEGRAM_CHAT_ID=... # your chat or channel id
python -m listing_monitor config.json
```

Use `--once` to run a single check from cron or Windows Task Scheduler.

## Example run

Against [books.toscrape.com](https://books.toscrape.com), a site made for scraping practice,
with `max_price: 30`:

```
books / 'mystery_3': 20 found, 11 match, 11 new     # first run: remembered, nothing sent
check finished, 0 sent
books / 'mystery_3': 20 found, 11 match, 0 new      # next run: nothing new yet
check finished, 0 sent
```

## Configuration

```json
{
  "interval_minutes": 10,
  "sources": [
    {"type": "css", "name": "books",
     "search_url": "https://books.toscrape.com/catalogue/category/books/{q}/index.html",
     "item": "article.product_pod", "title": "h3 a", "link": "h3 a", "price": ".price_color"}
  ],
  "queries": [
    {"text": "mystery_3", "max_price": 30, "sources": ["books"]}
  ]
}
```

`{q}` in `search_url` is replaced with the query text. A query can be limited to some sources
with `"sources"`; without it the query runs everywhere.

## Project layout

```
listing_monitor/
  sources.py    # eBay API, CSS and browser sources, price parsing
  filters.py    # Query: include / exclude words, price range
  store.py      # SQLite memory of already reported listings
  telegram.py   # message formatting, retry on rate limit
  __main__.py   # check loop and CLI
tests/
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Limitations

- Selectors are per site, so a redesign of a site means updating its config.
- Sites that show a captcha are skipped and logged; there is no captcha solving on purpose.
- The eBay source needs free developer keys from developer.ebay.com.

## License

MIT
