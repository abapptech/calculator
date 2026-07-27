"""
Парсер курса юаня (CNY) ВТБ → vtb_rate.json

Стратегия:
1. Сначала пробуем публичный API ВТБ (быстро, без браузера)
2. Если не отвечает — падаем на Playwright + HTML-парсинг страницы /yuan/

category=3 — курсы для интернет-банка и мобильного банка
type=1    — покупка/продажа за рубли (обычные тарифы)
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

RATE_FILE  = "vtb_rate.json"
DEBUG_HTML = "vtb_debug.html"
DEBUG_JSON = "vtb_debug.json"

API_URL  = "https://www.vtb.ru/api/currencyrates/table/optimized?category=3&type=1"
PAGE_URL = "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/yuan/"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/123.0.0.0 Safari/537.36")


# ── Способ 1: API ────────────────────────────────────────────────────────────
def try_api():
    """
    Пробуем получить курс через официальный API ВТБ.
    Возвращает {"buy": X, "sell": Y} или None.
    """
    print(f"[{datetime.now():%H:%M:%S}] Пробую API: {API_URL}")

    req = urllib.request.Request(API_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Referer": "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/yuan/",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", errors="replace")
            print(f"  ✓ API ответил: HTTP {r.status}, {len(body)} байт")
    except Exception as e:
        print(f"  ✗ API не ответил: {type(e).__name__}: {e}")
        return None

    # Сохраняем сырой ответ для отладки
    try:
        with open(DEBUG_JSON, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception:
        pass

    try:
        data = json.loads(body)
    except Exception as e:
        print(f"  ✗ Ответ не JSON: {e}")
        return None

    # Ищем CNY в ответе. Структура API может быть разной,
    # поэтому обходим рекурсивно и ищем объект с полями buy/sell/rate и упоминанием CNY/юань.
    rate = extract_cny_from_json(data)
    if rate:
        print(f"  ✓ Найден курс: buy={rate['buy']}, sell={rate['sell']}")
        return rate

    print("  ✗ CNY не найден в JSON")
    return None


def extract_cny_from_json(data):
    """
    Рекурсивно ищем в JSON объект курса юаня.
    Возможные варианты структуры:
    - {"CNY": {"buy": ..., "sell": ...}}
    - {"currency": "CNY", "buy": ..., "sell": ...}
    - вложенные списки/словари
    """
    results = []

    def walk(obj, ctx=""):
        if isinstance(obj, dict):
            # Определяем — не тот ли это словарь, что описывает курс
            keys = {k.lower() for k in obj.keys()}
            values_text = " ".join(str(v) for v in obj.values() if isinstance(v, (str, int, float)))

            # Признак что это словарь курса конкретной валюты
            is_currency_row = (
                # ISO код валюты
                any(k in obj for k in ["currency", "iso", "code", "isoCode", "charCode", "currencyCode"])
                # или в словаре есть buy/sell/purchase/sell/rate
                or (keys & {"buy", "sell", "purchase", "sale", "buyrate", "sellrate", "buy_rate", "sell_rate"})
            )
            is_cny = ("CNY" in values_text) or ("cny" in values_text.lower()) or ("юан" in values_text.lower()) or ("китайск" in values_text.lower())

            if is_currency_row and is_cny:
                buy = _find_num(obj, ["buy", "purchase", "buyrate", "buy_rate", "buyRate"])
                sell = _find_num(obj, ["sell", "sale", "sellrate", "sell_rate", "sellRate"])
                if buy and sell:
                    results.append({"buy": float(buy), "sell": float(sell)})

            # Рекурсивно
            for k, v in obj.items():
                walk(v, ctx + "/" + str(k))

        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, ctx + f"[{i}]")

    walk(data)

    # Выбираем самый разумный курс: buy < sell, разница < 3 руб, значения в диапазоне 5-50
    valid = [r for r in results if 5 < r["buy"] < 50 and 5 < r["sell"] < 50 and r["buy"] < r["sell"]]
    if valid:
        return valid[0]
    if results:
        return results[0]
    return None


def _find_num(obj, keys):
    for k in obj.keys():
        if k.lower() in [x.lower() for x in keys]:
            v = obj[k]
            if isinstance(v, (int, float)):
                return v
            if isinstance(v, str):
                try:
                    return float(v.replace(",", "."))
                except ValueError:
                    pass
    return None


# ── Способ 2: Playwright fallback ────────────────────────────────────────────
def try_playwright():
    """Fallback: открываем страницу /yuan/ через headless Chromium."""
    print(f"[{datetime.now():%H:%M:%S}] Fallback на Playwright")
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  ✗ Playwright не установлен")
        return None

    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(user_agent=UA, locale="ru-RU",
                                      viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print(f"  Открываю {PAGE_URL}")
        try:
            page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=60000)
        except PWTimeout:
            print("  ⚠️ Timeout domcontentloaded — пробую load...")
            try:
                page.goto(PAGE_URL, wait_until="load", timeout=60000)
            except PWTimeout:
                print("  ✗ Страница не открылась даже за 60 сек")
                browser.close()
                return None

        page.wait_for_timeout(6000)
        html = page.content()
        browser.close()

    try:
        with open(DEBUG_HTML, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass

    soup = BeautifulSoup(html, "html.parser")
    target = soup.find(string=lambda t: t and "500 000" in t)
    if target:
        row = target.parent
        for _ in range(6):
            if row.parent:
                row = row.parent
        row_text = row.get_text(" ", strip=True)
        nums = re.findall(r'\b(\d{1,2}[.,]\d{2})\b', row_text)
        nums = [float(n.replace(",", ".")) for n in nums]
        nums = [n for n in nums if 5 < n < 50]
        for i in range(len(nums) - 1):
            buy, sell = nums[i], nums[i+1]
            if buy < sell and (sell - buy) < 3:
                return {"buy": buy, "sell": sell}

    print("  ✗ HTML не содержит нужного тарифа")
    return None


# ── Main ─────────────────────────────────────────────────────────────────────
def save_rate_json(rate: dict):
    MSK = timezone(timedelta(hours=3))
    now_msk = datetime.now(MSK).strftime("%Y-%m-%d %H:%M МСК")
    data = {
        "cny_buy":  rate["buy"],
        "cny_sell": rate["sell"],
        "updated":  now_msk,
    }
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now(MSK).strftime('%H:%M:%S')} МСК] Сохранено в {RATE_FILE} ✅")
    print(f"  CNY покупка: {rate['buy']} | продажа: {rate['sell']}")


if __name__ == "__main__":
    rate = try_api() or try_playwright()
    if rate:
        save_rate_json(rate)
        print("✅ Готово!")
        sys.exit(0)
    else:
        print("⚠️ Курс юаня не найден ни через API, ни через HTML.")
        sys.exit(1)
