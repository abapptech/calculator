#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер каталога autohome.com.cn -> JSON для калькулятора abappcn.ru

Структура обхода:
  1) AsLeftMenu/As_LeftListNew.ashx      -> список марок (GB2312)
  2) price/brand-{brandId}.html          -> модели (车系) марки (GB2312)
  3) price/series-{seriesId}.html        -> комплектации + цена MSRP (GB2312, без обфускации)
  4) config/series/{seriesId}.html       -> дата выхода (上市时间, param id=8453) (UTF-8)

Фильтр: остаются только комплектации с датой выхода за последние N лет (по умолчанию 3).
"""

import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------- константы

BASE = "https://car.autohome.com.cn"

URL_BRANDS = BASE + "/AsLeftMenu/As_LeftListNew.ashx"
URL_BRAND = BASE + "/price/brand-{brand_id}.html"
URL_SERIES = BASE + "/price/series-{series_id}.html"
URL_CONFIG = BASE + "/config/series/{series_id}.html"

# id параметра "上市时间" во встроенном JSON config-страницы.
# Привязка к числовому id, т.к. текстовые названия параметров обфусцированы
# спанами вида <span class='hs_kw27_configCj'></span>
PARAM_ID_LAUNCH_DATE = 8453

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

DELAY_MIN = 1.2
DELAY_MAX = 2.6
RETRIES = 4
TIMEOUT = 20

log = logging.getLogger("autohome")


# ---------------------------------------------------------------- сеть

class Fetcher:
    """HTTP-клиент с задержками, ретраями и ротацией User-Agent."""

    def __init__(self, delay_min=DELAY_MIN, delay_max=DELAY_MAX):
        self.session = requests.Session()
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.requests_made = 0

    def _headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": BASE + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def get(self, url, params=None, encoding=None):
        """
        Возвращает текст страницы или None.
        encoding: 'gb18030' | 'utf-8' | None (автодетект)
        """
        last_err = None
        for attempt in range(1, RETRIES + 1):
            try:
                time.sleep(random.uniform(self.delay_min, self.delay_max))
                r = self.session.get(
                    url, params=params, headers=self._headers(), timeout=TIMEOUT
                )
                self.requests_made += 1

                if r.status_code == 200:
                    if encoding:
                        return r.content.decode(encoding, errors="replace")
                    return r.content.decode(
                        r.apparent_encoding or "utf-8", errors="replace"
                    )

                # 403/503 — вероятная антибот-реакция, ждём дольше
                if r.status_code in (403, 429, 503):
                    wait = 10 * attempt
                    log.warning(
                        "HTTP %s на %s — пауза %ss (попытка %s/%s)",
                        r.status_code, url, wait, attempt, RETRIES,
                    )
                    time.sleep(wait)
                    last_err = f"HTTP {r.status_code}"
                    continue

                last_err = f"HTTP {r.status_code}"
                log.warning("HTTP %s на %s", r.status_code, url)

            except requests.RequestException as e:
                last_err = str(e)
                log.warning(
                    "Ошибка сети на %s: %s (попытка %s/%s)", url, e, attempt, RETRIES
                )
                time.sleep(4 * attempt)

        log.error("Не удалось получить %s: %s", url, last_err)
        return None


# ---------------------------------------------------------------- утилиты

def clean_text(s):
    """Убирает обфусцирующие спаны, теги и лишние пробелы."""
    if not s:
        return ""
    s = re.sub(r"<span[^>]*class='hs_kw[^']*'[^>]*>\s*</span>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def wan_to_cny(value_str):
    """'25.80' (万元) -> 258000 (юаней). None если не число."""
    if not value_str:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(value_str))
    if not m:
        return None
    return int(round(float(m.group(1)) * 10000))


def parse_launch_date(raw):
    """'2026.01' -> (2026, 1). None если не распознано."""
    if not raw:
        return None
    m = re.search(r"(20\d{2})[.\-/年]?\s*(\d{1,2})?", str(raw))
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    if not 1 <= month <= 12:
        month = 1
    return year, month


def months_ago(year, month, now=None):
    now = now or datetime.utcnow()
    return (now.year - year) * 12 + (now.month - month)


# ---------------------------------------------------------------- шаг 1: марки

RE_BRAND = re.compile(
    r"<li\s*id='b(\d+)'>.*?</i>([^<]*)<em>\((\d+)\)</em>", re.S
)


def fetch_brands(fetcher):
    """[{'brand_id': 15, 'name': '宝马', 'spec_count': 1900}, ...]"""
    html = fetcher.get(
        URL_BRANDS,
        params={"typeId": "1", "brandId": "0", "fctId": "0", "seriesId": "0"},
        encoding="gb18030",
    )
    if not html:
        return []

    brands = []
    for bid, name, count in RE_BRAND.findall(html):
        name = clean_text(name)
        if not name:
            continue
        brands.append(
            {"brand_id": int(bid), "name": name, "spec_count": int(count)}
        )
    log.info("Найдено марок: %s", len(brands))
    return brands


# ---------------------------------------------------------------- шаг 2: модели

RE_SERIES = re.compile(
    r'<a\s+href="/price/series-(\d+)[^"]*\.html[^"]*"\s+title="([^"]+)"', re.S
)


# <title>【宝马】BMW报价_...  -> латинское имя марки для читаемости в UI
RE_BRAND_LATIN = re.compile(r"<title>【[^】]+】([A-Za-z0-9][A-Za-z0-9\s\-\.·&]*)")


def fetch_brand_page(fetcher, brand_id, include_discontinued=False):
    """
    Один запрос к странице марки -> латинское имя марки + список моделей.
    -> {'latin': str|None, 'series': [...]}
    """
    html = fetcher.get(URL_BRAND.format(brand_id=brand_id), encoding="gb18030")
    if not html:
        return {"latin": None, "series": []}

    latin_m = RE_BRAND_LATIN.search(html)
    latin = latin_m.group(1).strip() if latin_m else None
    if latin:
        latin = re.sub(r"(报价|图片|汽车).*$", "", latin).strip() or None

    return {
        "latin": latin,
        "series": _parse_series(html, include_discontinued),
    }


def fetch_series(fetcher, brand_id, include_discontinued=False):
    """
    Модели (车系) марки.
    Снятые с производства (в title стоит '停售') отбрасываются по умолчанию —
    это заметно сокращает объём дальнейших запросов.
    """
    html = fetcher.get(URL_BRAND.format(brand_id=brand_id), encoding="gb18030")
    if not html:
        return []
    return _parse_series(html, include_discontinued)


def _parse_series(html, include_discontinued=False):

    seen, series = set(), []
    for sid, title in RE_SERIES.findall(html):
        sid = int(sid)
        if sid in seen:
            continue
        title = clean_text(title)
        discontinued = "停售" in title
        if discontinued and not include_discontinued:
            continue
        seen.add(sid)
        series.append(
            {
                "series_id": sid,
                "name": re.sub(r"\s*\(停售\)\s*", "", title).strip(),
                "discontinued": discontinued,
            }
        )
    return series


# ---------------------------------------------------------------- шаг 3: цены

RE_SPEC_BLOCK = re.compile(r'data-value="(\d+)"')


def fetch_specs_with_prices(fetcher, series_id):
    """
    Комплектации модели с ценой MSRP.
    Берём со страницы price/series-*.html — там текст НЕ обфусцирован.
    -> {spec_id: {'name': ..., 'price_cny': ...}}
    """
    html = fetcher.get(URL_SERIES.format(series_id=series_id), encoding="gb18030")
    if not html:
        return {}

    specs = {}
    # режем страницу на блоки по data-value="{specid}"
    positions = [(m.group(1), m.start()) for m in RE_SPEC_BLOCK.finditer(html)]
    for i, (spec_id, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else min(
            start + 6000, len(html)
        )
        chunk = html[start:end]

        name_m = re.search(
            r"/spec/" + spec_id + r"/[^\"']*[\"'][^>]*>([^<]+)</a>", chunk
        )
        if not name_m:
            continue
        name = clean_text(name_m.group(1))
        if not name:
            continue

        price = None
        guid_m = re.search(
            r'class="interval01-list-guidance".*?(\d+(?:\.\d+)?)\s*万', chunk, re.S
        )
        if guid_m:
            price = wan_to_cny(guid_m.group(1))

        specs[int(spec_id)] = {"name": name, "price_cny": price}

    return specs


# ---------------------------------------------------------------- шаг 4: даты

def _extract_config_json(html):
    """Вытаскивает объект `var config = {...};` со сбалансированными скобками."""
    anchor = html.find("var config = {")
    if anchor == -1:
        return None
    start = html.find("{", anchor)
    depth, in_str, esc = 0, False, False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = html[start : i + 1]
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    log.warning("config JSON не распарсился: %s", e)
                    return None
    return None


def fetch_launch_dates(fetcher, series_id):
    """
    Даты выхода комплектаций: {spec_id: '2026.01'}
    Источник — config-страница (UTF-8), параметр id=8453.
    """
    html = fetcher.get(URL_CONFIG.format(series_id=series_id), encoding="utf-8")
    if not html:
        return {}
    cfg = _extract_config_json(html)
    return _dates_from_config(cfg) if cfg else {}


def _dates_from_config(cfg):
    result = cfg.get("result") or {}
    dates = {}
    for group in result.get("paramtypeitems", []) or []:
        for item in group.get("paramitems", []) or []:
            if item.get("id") != PARAM_ID_LAUNCH_DATE:
                continue
            for v in item.get("valueitems", []) or []:
                spec_id = v.get("specid")
                value = clean_text(v.get("value"))
                if spec_id and value:
                    dates[int(spec_id)] = value
    return dates


def fetch_series_config(fetcher, series_id):
    """
    ОДИН запрос к config-странице даёт сразу всё: названия комплектаций,
    цены и даты выхода. Используется как основной (дешёвый) проход —
    большинство моделей отсеется по дате, и второй запрос им не понадобится.

    -> {spec_id: {'name': str, 'price_cny': int|None, 'launch_raw': str|None}}
    """
    html = fetcher.get(URL_CONFIG.format(series_id=series_id), encoding="utf-8")
    if not html:
        return {}

    cfg = _extract_config_json(html)
    if not cfg:
        return {}

    result = cfg.get("result") or {}
    groups = result.get("paramtypeitems", []) or []
    if not groups:
        return {}

    first_items = groups[0].get("paramitems", []) or []

    names, prices = {}, {}
    for idx, item in enumerate(first_items):
        vals = item.get("valueitems", []) or []
        if not vals:
            continue
        cleaned = {
            v.get("specid"): clean_text(v.get("value"))
            for v in vals
            if v.get("specid")
        }
        non_empty = [x for x in cleaned.values() if x]
        if not non_empty:
            continue

        # цена: большинство значений — числа вида 25.80.
        # НЕ требуем "все", т.к. у части комплектаций стоит "暂无报价";
        # дополнительно фиксируем позицию — столбец цены идёт сразу за названием.
        numeric = [x for x in non_empty if re.fullmatch(r"\d+(?:\.\d+)?", x)]
        mostly_numeric = len(numeric) >= max(1, int(len(non_empty) * 0.5))
        if mostly_numeric and not prices and names and idx <= 2:
            prices = {k: wan_to_cny(v) for k, v in cleaned.items()}
        elif not names:
            names = cleaned

    dates = _dates_from_config(cfg)

    specs = {}
    for spec_id in set(list(names) + list(prices) + list(dates)):
        specs[int(spec_id)] = {
            "name": names.get(spec_id, ""),
            "price_cny": prices.get(spec_id),
            "launch_raw": dates.get(spec_id),
        }
    return specs
