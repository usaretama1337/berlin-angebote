#!/bin/sh
# Для macOS и Linux
cd "$(dirname "$0")"
python3 scraper/scrape.py && python3 scraper/publish.py
