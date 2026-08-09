"""
Обновление курса юаня (CNY) ВТБ -> vtb_rate.json

Источники (по приоритету):
  1. VDS-прокси (российский IP) -> официальный API ВТБ, категория 3
     "В интернет-банке и мобильном банке" — реальный курс.
  2. Бэкенд abapp.tech — резерв (может отдавать приближение по курсу ЦБ,
     если сам не достучался до ВТБ).

Файл vtb_rate.json коммитится в репозиторий workflow-шагом и служит
кэшем для калькулятора.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

RATE_FILE = "vtb_rate.json"
SOURCES = [
    ("VDS-прокси (API ВТБ, категория 3)",
     "http://188.120.231.224:9999/vtb-rate?token=EhSV1n_BElqWN4K8SpNnZWjwV2uQaTvw"),
    ("abapp.tech (резерв)",
     "https://www.abapp.tech/api/car/vtb-rate"),
]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

MSK = timezone(timedelta(hours=3))


def try_source(name: str, url: str) -> dict | None:
    print(f"[{datetime.now(MSK):%H:%M:%S} МСК] Пробую: {name}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        buy, sell = data.get("cny_buy"), data.get("cny_sell")
        if not (isinstance(buy, (int, float)) and isinstance(sell, (int, float))):
            print(f"  ⚠️ Нет cny_buy/cny_sell в ответе: {data}")
            return None
        if not (5 < buy < 50 and 5 < sell < 50):
            print(f"  ⚠️ Подозрительные значения: buy={buy}, sell={sell}")
            return None
        src = data.get("source", "")
        print(f"  ✅ CNY покупка: {buy} | продажа: {sell}"
              + (f" | source: {src}" if src else ""))
        return {"cny_buy": buy, "cny_sell": sell}
    except Exception as e:
        print(f"  ⚠️ Не удалось: {e}")
        return None


def save_rate_json(rate: dict):
    now_msk = datetime.now(MSK).strftime("%Y-%m-%d %H:%M МСК")
    data = {
        "cny_buy": rate["cny_buy"],
        "cny_sell": rate["cny_sell"],
        "updated": now_msk,
    }
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now(MSK):%H:%M:%S} МСК] Сохранено в {RATE_FILE} ✅")


if __name__ == "__main__":
    for name, url in SOURCES:
        rate = try_source(name, url)
        if rate:
            save_rate_json(rate)
            print("✅ Готово!")
            sys.exit(0)
    print("⚠️ Ни один источник не отдал курс.")
    sys.exit(1)
