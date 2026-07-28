"""Тестовый скрипт: проверка прямого доступа к ВТБ с GitHub Actions runner"""
import urllib.request
import http.cookiejar
import json
import sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
PAGE_URL = "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/yuan/"
API_URL = "https://www.vtb.ru/api/currencyrates/table/optimized?category=3&type=1"

print("=== Тест 1: прямой запрос к странице /yuan/ (без cookies) ===")
try:
    req = urllib.request.Request(PAGE_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        print(f"HTTP {r.status}, {len(r.read())} байт")
except Exception as e:
    print(f"ОШИБКА: {type(e).__name__}: {e}")

print()
print("=== Тест 2: прямой запрос к API (без cookies) ===")
try:
    req = urllib.request.Request(API_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": PAGE_URL,
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode()
        print(f"HTTP {r.status}, {len(body)} байт")
        print(body[:300])
except Exception as e:
    print(f"ОШИБКА: {type(e).__name__}: {e}")

print()
print("=== Тест 3: cookies с /yuan/ + запрос к API ===")
try:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req_page = urllib.request.Request(PAGE_URL, headers={"User-Agent": UA})
    with opener.open(req_page, timeout=20) as r:
        print(f"Страница: HTTP {r.status}")
    req_api = urllib.request.Request(API_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
    })
    with opener.open(req_api, timeout=20) as r:
        body = r.read().decode()
        print(f"API с cookies: HTTP {r.status}, {len(body)} байт")
        data = json.loads(body)
        cny = [x for x in data.get("rates", []) if x.get("currency1", {}).get("code") == "CNY"]
        for c in cny:
            print(f"  CNY: bid={c.get('bid')}, offer={c.get('offer')}, tooltip={c.get('tooltip')}")
except Exception as e:
    print(f"ОШИБКА: {type(e).__name__}: {e}")
