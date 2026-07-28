"""
Обновление курса юаня (CNY) ВТБ → vtb_rate.json

Источник: собственный API-эндпоинт на abapp.tech, который сам получает
курс ВТБ (обходя блокировку через VDS с российским IP + cookies-сессию).

Это просто клиент, который раз в N минут (по расписанию GitHub Actions)
читает готовый JSON и коммитит его в репозиторий как резервный кэш —
на случай если основной эндпоинт abapp.tech станет временно недоступен,
калькулятор сможет упасть на этот файл.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

RATE_FILE = "vtb_rate.json"
API_URL = "https://www.abapp.tech/api/car/vtb-rate"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")


def fetch_rate():
    print(f"[{datetime.now():%H:%M:%S}] Запрашиваю {API_URL}")
    req = urllib.request.Request(API_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8")
        print(f"  HTTP {r.status}, {len(body)} байт")

    data = json.loads(body)
    buy = data.get("cny_buy")
    sell = data.get("cny_sell")
    if buy is None or sell is None:
        raise ValueError(f"Ответ не содержит cny_buy/cny_sell: {data}")

    print(f"  CNY покупка: {buy} | продажа: {sell} | updated (источник): {data.get('updated')}")
    return {"cny_buy": buy, "cny_sell": sell}


def save_rate_json(rate: dict):
    MSK = timezone(timedelta(hours=3))
    now_msk = datetime.now(MSK).strftime("%Y-%m-%d %H:%M МСК")
    data = {
        "cny_buy": rate["cny_buy"],
        "cny_sell": rate["cny_sell"],
        "updated": now_msk,
    }
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now(MSK).strftime('%H:%M:%S')} МСК] Сохранено в {RATE_FILE} ✅")


if __name__ == "__main__":
    try:
        rate = fetch_rate()
        save_rate_json(rate)
        print("✅ Готово!")
        sys.exit(0)
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        sys.exit(1)
