"""
Парсер курса юаня (CNY) ВТБ → vtb_rate.json
Страница: /obmen-valjuty/yuan/ (курс юаня на сегодня)
Режим: В интернет-банке и мобильном банке
"""

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import re
import sys

URL       = "https://www.vtb.ru/personal/platezhi-i-perevody/obmen-valjuty/yuan/"
RATE_FILE = "vtb_rate.json"
DEBUG_HTML = "vtb_debug.html"


def try_click_online_mode(page):
    """
    Пробуем переключить дропдаун на 'В интернет-банке и мобильном банке'.
    На новой странице /yuan/ дропдаун может быть встроен в блок курсов.
    Если не получается — возвращаем False и работаем с тем что есть.
    """
    # Пробуем разные варианты клика
    candidates = [
        "text=В интернет-банке и мобильном банке",
        "text=В интернет-банке",
        "text=Выберите способ обмена",
    ]
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=5000)
                page.wait_for_timeout(1500)
                # После клика возможно открылась опция — кликаем повторно если есть
                sub = page.query_selector("text=В интернет-банке и мобильном банке")
                if sub and sub.is_visible():
                    sub.click(timeout=5000)
                    page.wait_for_timeout(2500)
                return True
        except Exception as e:
            print(f"  ! Клик '{sel}' не сработал: {type(e).__name__}")
    return False


def extract_rate_from_html(html):
    """
    Извлекаем курс покупки/продажи из HTML.
    Стратегии — от самой точной к самой общей.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Стратегия 1: строка тарифа '500 000' — как было в старом парсере
    target = soup.find(string=lambda t: t and "500 000" in t)
    if target:
        row = target.parent
        for _ in range(6):
            if row.parent:
                row = row.parent
        row_text = row.get_text(" ", strip=True)
        print(f"  → Стратегия 1 (500 000): найдена строка длиной {len(row_text)} символов")
        nums = _extract_rate_pair(row_text)
        if nums:
            return nums, "strategy_1_500000"

    # Стратегия 2: ищем любые упоминания '500' с числами рядом (для новых тарифов)
    for text in soup.find_all(string=lambda t: t and re.search(r'\b500\s*000\b|\bдо\s+500\b', t or '')):
        row = text.parent
        for _ in range(6):
            if row.parent:
                row = row.parent
        row_text = row.get_text(" ", strip=True)
        nums = _extract_rate_pair(row_text)
        if nums:
            print(f"  → Стратегия 2 (упоминание 500): найдено")
            return nums, "strategy_2_500_mention"

    # Стратегия 3: ищем таблицу с 'юань' или 'CNY' и берём первую пару курсов
    for keyword in ['юан', 'CNY', 'китайск']:
        for text in soup.find_all(string=lambda t, k=keyword: t and k.lower() in t.lower()):
            row = text.parent
            for _ in range(8):
                if row.parent:
                    row = row.parent
            row_text = row.get_text(" ", strip=True)
            nums = _extract_rate_pair(row_text)
            if nums:
                print(f"  → Стратегия 3 (упоминание '{keyword}'): найдено")
                return nums, f"strategy_3_{keyword}"

    # Стратегия 4: собираем все числа вида XX.XX и ищем логичные пары
    all_text = soup.get_text(" ", strip=True)
    nums = _extract_rate_pair(all_text)
    if nums:
        print(f"  → Стратегия 4 (весь текст): найдено")
        return nums, "strategy_4_all_text"

    return None, None


def _extract_rate_pair(text):
    """
    Ищем 2 числа формата XX.XX в диапазоне 5-50 (курс юаня).
    Возвращаем первую логичную пару (buy < sell).
    """
    numbers = re.findall(r'\b(\d{1,2}[.,]\d{2})\b', text)
    numbers = [float(n.replace(",", ".")) for n in numbers]
    numbers = [n for n in numbers if 5 < n < 50]

    if len(numbers) < 2:
        return None

    # Ищем первую пару где buy < sell и разница разумна (< 3 руб)
    for i in range(len(numbers) - 1):
        buy, sell = numbers[i], numbers[i+1]
        if buy < sell and (sell - buy) < 3:
            return {"buy": buy, "sell": sell}

    # Fallback: просто первые два числа
    return {"buy": numbers[0], "sell": numbers[1]}


def parse_cny_rate():
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

        print(f"[{datetime.now():%H:%M:%S}] Открываю {URL}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except PWTimeout:
            print("  ⚠️ Timeout domcontentloaded — пробую load...")
            page.goto(URL, wait_until="load", timeout=60000)

        # Ждём загрузки динамического контента
        page.wait_for_timeout(6000)

        print(f"[{datetime.now():%H:%M:%S}] Пробую переключить на 'В интернет-банке'...")
        clicked = try_click_online_mode(page)
        print(f"  Результат клика: {clicked}")

        # Даём странице догрузиться после клика
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    # Сохраняем HTML для отладки
    try:
        with open(DEBUG_HTML, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[{datetime.now():%H:%M:%S}] HTML сохранён в {DEBUG_HTML} ({len(html)} символов)")
    except Exception as e:
        print(f"  ! Не смог сохранить debug HTML: {e}")

    print(f"[{datetime.now():%H:%M:%S}] Извлекаю курс из HTML...")
    rate, strategy = extract_rate_from_html(html)

    if rate:
        print(f"  ✅ Курс найден стратегией: {strategy}")
        print(f"     buy={rate['buy']}, sell={rate['sell']}")
        return rate

    print(f"  ⚠️ Ни одна стратегия не сработала")
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
        sys.exit(0)
    else:
        print("⚠️ Курс юаня не найден.")
        sys.exit(1)  # Явный exit(1) чтобы workflow помечался как failure
