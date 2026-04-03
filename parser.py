"""
Парсер курса юаня (CNY) ВТБ → vtb_rate.json
Режим: В интернет-банке и мобильном банке
"""

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import re

URL       = "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/"
RATE_FILE = "vtb_rate.json"


def parse_cny_rate() -> dict | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/123.0.0.0 Safari/537.36",
            locale="ru-RU",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print(f"[{datetime.now():%H:%M:%S}] Открываю страницу ВТБ...")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except PWTimeout:
            print("⚠️ Timeout при загрузке — пробую load...")
            page.goto(URL, wait_until="load", timeout=60000)

        page.wait_for_timeout(5000)

        print(f"[{datetime.now():%H:%M:%S}] Выбираю режим 'В интернет-банке'...")
        try:
            page.click("text=Выберите способ обмена", timeout=10000)
            page.wait_for_timeout(1500)
            page.click("text=В интернет-банке и мобильном банке", timeout=10000)
            page.wait_for_timeout(4000)
        except PWTimeout:
            print("⚠️ Не смог кликнуть по дропдауну — попробую читать HTML как есть")

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    target_tag = soup.find(string=lambda t: t and "500 000" in t)

    if not target_tag:
        print("⚠️ Строка с 500 000 не найдена.")
        return None

    row = target_tag.parent
    for _ in range(6):
        row = row.parent

    row_text = row.get_text(" ", strip=True)
    print(f"[{datetime.now():%H:%M:%S}] Найдена строка: {row_text}")

    numbers = re.findall(r'\b(\d{1,2}[.,]\d{2})\b', row_text)
    numbers = [float(n.replace(",", ".")) for n in numbers
               if 5 < float(n.replace(",", ".")) < 50]

    if len(numbers) >= 2:
        return {"buy": numbers[0], "sell": numbers[1]}

    print(f"⚠️ Не удалось извлечь курс: {row_text}")
    return None


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
    rate = parse_cny_rate()
    if rate:
        save_rate_json(rate)
        print("✅ Готово!")
    else:
        print("⚠️ Курс юаня не найден.")
