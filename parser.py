"""
Парсер курса юаня (CNY) ВТБ → vtb_rate.json
Режим: В интернет-банке и мобильном банке
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re

URL       = "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/"
RATE_FILE = "vtb_rate.json"


def parse_cny_rate() -> dict | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"[{datetime.now():%H:%M:%S}] Открываю страницу ВТБ...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)

        print(f"[{datetime.now():%H:%M:%S}] Выбираю режим 'В интернет-банке'...")
        page.click("text=Выберите способ обмена")
        page.wait_for_timeout(1500)
        page.click("text=В интернет-банке и мобильном банке")
        page.wait_for_timeout(3000)

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
    data = {
        "cny_buy":  rate["buy"],
        "cny_sell": rate["sell"],
        "updated":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now():%H:%M:%S}] Сохранено в {RATE_FILE} ✅")
    print(f"  CNY покупка: {rate['buy']} | продажа: {rate['sell']}")


if __name__ == "__main__":
    rate = parse_cny_rate()
    if rate:
        save_rate_json(rate)
        print("✅ Готово!")
    else:
        print("⚠️ Курс юаня не найден.")
