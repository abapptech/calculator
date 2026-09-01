#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер технических характеристик (объём ДВС, мощность ДВС) для всех комплектаций
из autohome/data/specs/*.json.

Данные берёт с car.autohome.com.cn/config/series/{series_id}.html
Сохраняет в autohome/data/manual_specs.json — без перезаписи уже имеющихся записей.
Электро- и гибридные комплектации пропускает (поле kw оставляет пустым).

Поддерживает инкрементальный запуск:
  - Сохраняет прогресс в autohome/data/.specs_progress.json
  - При следующем запуске продолжает с места остановки
  - Запускать можно несколько раз, пока не обработаны все серии

Запуск:
    python autohome/specs_scraper.py --data-dir autohome/data
"""

import argparse
import json
import logging
import random
import re
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("specs")

BASE = "https://car.autohome.com.cn"
URL_CONFIG = BASE + "/config/series/{series_id}.html"

# IDs параметров в config-странице autohome
PARAM_CC_ML  = 1182   # объём двигателя в мл
PARAM_KW     = 1185   # максимальная мощность ДВС (кВт)
PARAM_FUEL   = 1149   # тип топлива / энергии

# Типы топлива, которые мы пропускаем (электро и гибриды всех видов)
SKIP_FUEL_KEYWORDS = ["纯电", "电动", "增程", "插电混动", "插电式混合"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

DELAY_MIN = 1.5
DELAY_MAX = 3.0
RETRIES = 4
TIMEOUT = 25


def get_headers(series_id):
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{BASE}/price/series-{series_id}.html",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def fetch_config_html(series_id):
    url = URL_CONFIG.format(series_id=series_id)
    last_err = None
    for attempt in range(1, RETRIES + 1):
        wait = random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(wait)
        try:
            r = requests.get(url, headers=get_headers(series_id), timeout=TIMEOUT)
            if r.status_code == 200 and len(r.content) > 10000:
                return r.content.decode("utf-8", errors="replace")
            if r.status_code in (404, 410):
                log.debug("404/410 series %s", series_id)
                return None
            log.warning("HTTP %s series %s (attempt %s/%s)", r.status_code, series_id, attempt, RETRIES)
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            log.warning("Network error series %s: %s (attempt %s/%s)", series_id, e, attempt, RETRIES)
            last_err = str(e)
            time.sleep(min(wait * 2, 10))
    log.error("Failed series %s: %s", series_id, last_err)
    return None


def extract_config_json(html):
    """Извлекает var config = {...} из HTML."""
    anchor = html.find("var config = {")
    if anchor == -1:
        return None
    start = html.find("{", anchor)
    if start == -1:
        return None
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
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def clean_value(v):
    """Убирает HTML-теги и пробелы из значения."""
    if not v:
        return ""
    return re.sub(r"<[^>]+>", "", str(v)).strip()


def parse_float(s):
    """Парсит число из строки вида '1987', '2.0', '-'."""
    s = clean_value(s)
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def should_skip_fuel(fuel_str):
    """Возвращает True если это электро/гибрид — пропускаем мощность ДВС."""
    if not fuel_str:
        return False
    for kw in SKIP_FUEL_KEYWORDS:
        if kw in fuel_str:
            return True
    return False


def parse_series_specs(html):
    """
    Парсит config-страницу серии.
    Возвращает dict: {spec_id: {"cc": int|None, "kw": float|None, "skip": bool}}
    skip=True означает электро/гибрид (мощность ДВС оставляем пустой)
    """
    cfg = extract_config_json(html)
    if not cfg:
        return {}

    result = cfg.get("result") or {}
    groups = result.get("paramtypeitems") or []

    # Собираем все spec_id из первой группы
    all_spec_ids = set()
    for g in groups:
        for item in g.get("paramitems") or []:
            for v in item.get("valueitems") or []:
                sid = v.get("specid")
                if sid:
                    all_spec_ids.add(int(sid))

    # Построим lookup: param_id -> {spec_id -> value}
    param_values = {}
    for g in groups:
        for item in g.get("paramitems") or []:
            pid = item.get("id")
            if pid is None or pid < 0:
                continue
            pid = int(pid)
            if pid not in (PARAM_CC_ML, PARAM_KW, PARAM_FUEL):
                continue
            if pid not in param_values:
                param_values[pid] = {}
            for v in item.get("valueitems") or []:
                sid = v.get("specid")
                val = clean_value(v.get("value"))
                if sid:
                    param_values[pid][int(sid)] = val

    specs = {}
    fuel_map = param_values.get(PARAM_FUEL, {})
    cc_map   = param_values.get(PARAM_CC_ML, {})
    kw_map   = param_values.get(PARAM_KW, {})

    for spec_id in all_spec_ids:
        fuel = fuel_map.get(spec_id, "")
        skip = should_skip_fuel(fuel)

        cc_ml = parse_float(cc_map.get(spec_id))
        cc = int(round(cc_ml)) if cc_ml and cc_ml > 50 else None

        if skip:
            kw = None
        else:
            kw_val = parse_float(kw_map.get(spec_id))
            kw = round(kw_val, 1) if kw_val and kw_val > 0 else None

        if cc or kw:
            specs[spec_id] = {"cc": cc, "kw": kw, "skip_motor": skip}

    return specs


def collect_all_series(data_dir):
    """Собирает все (series_id, [spec_ids]) из specs/*.json."""
    specs_dir = data_dir / "specs"
    series_map = {}
    for path in sorted(specs_dir.glob("*.json")):
        series_id = int(path.stem)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        trims = data.get("trims", [])
        spec_ids = [t["spec_id"] for t in trims if t.get("spec_id")]
        if spec_ids:
            series_map[series_id] = spec_ids
    return series_map


def main():
    parser = argparse.ArgumentParser(description="Scrape engine specs from autohome config pages")
    parser.add_argument("--data-dir", default="autohome/data", help="Path to data directory")
    parser.add_argument("--max-series", type=int, default=0, help="Limit series count (0=all, for testing)")
    parser.add_argument("--reset", action="store_true", help="Reset progress and start over")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    manual_path = data_dir / "manual_specs.json"
    progress_path = data_dir / ".specs_progress.json"

    # Загружаем существующие manual_specs
    if manual_path.exists():
        existing = json.loads(manual_path.read_text(encoding="utf-8"))
        # Убираем _comment и другие не-числовые ключи
        manual = {k: v for k, v in existing.items() if k.lstrip("-").isdigit()}
        meta = {k: v for k, v in existing.items() if not k.lstrip("-").isdigit()}
    else:
        manual = {}
        meta = {"_comment": "Ручные данные: cc (объём см³), kw (мощность кВт). Ключ = spec_id. Не перезаписывается парсером цен."}

    # Загружаем прогресс
    if not args.reset and progress_path.exists():
        progress = json.loads(progress_path.read_text())
    else:
        progress = {"done_series": [], "total": 0, "processed_specs": 0}

    done_series = set(progress.get("done_series", []))

    # Собираем все серии
    log.info("Scanning specs directory...")
    series_map = collect_all_series(data_dir)
    total_series = len(series_map)
    log.info("Found %d series with trims", total_series)

    pending = [sid for sid in sorted(series_map) if sid not in done_series]
    if args.max_series:
        pending = pending[:args.max_series]

    log.info("Pending: %d series (done: %d)", len(pending), len(done_series))

    added = 0
    for i, series_id in enumerate(pending, 1):
        spec_ids_in_series = series_map[series_id]

        # Если все spec_id этой серии уже покрыты в manual — пропускаем
        uncovered = [sid for sid in spec_ids_in_series if str(sid) not in manual]
        if not uncovered:
            log.info("[%d/%d] series %d — all %d specs already in manual_specs, skipping",
                     i, len(pending), series_id, len(spec_ids_in_series))
            done_series.add(series_id)
            continue

        log.info("[%d/%d] Fetching series %d (%d specs, %d uncovered)...",
                 i, len(pending), series_id, len(spec_ids_in_series), len(uncovered))

        html = fetch_config_html(series_id)
        if not html:
            log.warning("No HTML for series %d, skipping", series_id)
            done_series.add(series_id)
            continue

        parsed = parse_series_specs(html)
        log.info("  Parsed %d specs with engine data", len(parsed))

        for spec_id, data in parsed.items():
            key = str(spec_id)
            if key in manual:
                continue  # не перезаписываем существующие
            entry = {}
            if data.get("cc"):
                entry["cc"] = data["cc"]
            if data.get("kw"):
                entry["kw"] = data["kw"]
            if data.get("skip_motor"):
                entry["skip_motor"] = True
            if entry:
                manual[key] = entry
                added += 1

        done_series.add(series_id)

        # Сохраняем прогресс и manual_specs каждые 10 серий
        if i % 10 == 0 or i == len(pending):
            output = {**meta, **manual}
            manual_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            progress["done_series"] = sorted(done_series)
            progress["total"] = total_series
            progress["processed_specs"] = len(manual)
            progress_path.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
            log.info("Saved progress: %d series done, %d specs total, %d added this run",
                     len(done_series), len(manual), added)

    # Финальное сохранение
    output = {**meta, **manual}
    manual_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    progress["done_series"] = sorted(done_series)
    progress["total"] = total_series
    progress["processed_specs"] = len(manual)
    progress_path.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")

    remaining = total_series - len(done_series)
    log.info("Done. Added %d new specs this run. Remaining series: %d", added, remaining)
    if remaining > 0:
        log.info("Run again to continue (progress is saved)")


if __name__ == "__main__":
    main()
