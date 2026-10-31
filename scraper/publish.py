"""Загружает site/offers.json в репозиторий на GitHub, после чего сайт обновляется.

Нужен токен GitHub в файле github_token.txt в корне проекта (как его
получить, написано в README). Этот файл нельзя загружать на GitHub.
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from config import GITHUB_REPO

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "github_token.txt"
LOCAL_FILE = ROOT / "site" / "offers.json"
REMOTE_PATH = "site/offers.json"


def request(method, url, token, body=None):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "berlin-angebote",
    }, data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read() or b"{}")


def main():
    if "/" not in GITHUB_REPO or "ВАШ-ЛОГИН" in GITHUB_REPO:
        sys.exit("Укажите свой репозиторий в GITHUB_REPO в scraper/config.py")
    if not TOKEN_FILE.exists():
        sys.exit(f"Не найден файл с токеном: {TOKEN_FILE}")
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{REMOTE_PATH}"

    sha = None
    try:
        sha = request("GET", api, token).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.exit(f"GitHub не ответил ({e.code}). Проверьте токен и GITHUB_REPO.")

    body = {
        "message": "Обновлены акции",
        "content": base64.b64encode(LOCAL_FILE.read_bytes()).decode(),
    }
    if sha:
        body["sha"] = sha
    try:
        request("PUT", api, token, body)
    except urllib.error.HTTPError as e:
        sys.exit(f"Не удалось загрузить offers.json ({e.code}). "
                 "Проверьте, что у токена есть право Contents: Read and write.")
    print("offers.json загружен на GitHub, сайт обновится через 1–2 минуты.")


if __name__ == "__main__":
    main()
