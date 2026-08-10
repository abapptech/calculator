#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка каталога autohome (авто не старше N лет) в JSON для калькулятора.

Инкрементальный режим: состояние обхода хранится в state.json, поэтому
запуск можно прерывать и продолжать — это позволяет уложиться в лимиты
GitHub Actions, разбив полный обход на несколько запусков.

Примеры:
  python main.py --years 3 --time-budget 240        # полный обход, 4 часа максимум
  python main.py --brands 15,456 --time-budget 10   # тест на двух марках
  python main.py --reset                            # начать обход заново
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from translate import enrich_full_dump, enrich_index, enrich_spec_file
from parser import (
    Fetcher,
    fetch_brands,
    fetch_brand_page,
    fetch_launch_dates,
    fetch_series_config,
    fetch_specs_with_prices,
    months_ago,
    parse_launch_date,
)

HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"
OUTPUT_FILE = HERE / "data" / "autohome_prices.json"

log = logging.getLogger("main")


# ---------------------------------------------------------------- состояние

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("state.json повреждён — начинаю заново")
    return {
        "started_at": None,
        "brands": None,          # список марок (кэшируется между запусками)
        "pending_brands": None,  # brand_id, которые ещё не обработаны
        "series_queue": [],      # [{brand_id, brand_name, brand_latin, series_id, series_name}]
        "collected": {},         # brand_id -> {brand, models:[...]}
        "stats": {"requests": 0, "series_done": 0, "series_kept": 0},
    }


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------- сборка

def collect_series(fetcher, series_meta, years, now):
    """
    Обрабатывает одну модель в два этапа, чтобы экономить запросы:

      1) config-страница -> только даты выхода (дёшево). Если ни одна
         комплектация не проходит фильтр по возрасту, на этом и останавливаемся.
      2) price-страница   -> названия и цены. Берём именно оттуда, т.к. там
         текст НЕ обфусцирован, а на config-странице столбец цены
         распознаётся ненадёжно (у части комплектаций стоит "暂无报价").

    -> dict модели или None, если ничего не прошло фильтр.
    """
    limit_months = years * 12
    series_id = series_meta["series_id"]

    dates_raw = fetch_launch_dates(fetcher, series_id)
    if not dates_raw:
        return None

    fresh, dates_found = {}, []
    for spec_id, raw in dates_raw.items():
        parsed = parse_launch_date(raw)
        if not parsed:
            continue
        year, month = parsed
        dates_found.append((year, month))
        age = months_ago(year, month, now)
        if age > limit_months or age < -6:  # -6: допускаем анонсы на будущее
            continue
        fresh[spec_id] = f"{year:04d}.{month:02d}"

    if not fresh:
        return None

    # второй запрос — только для моделей, прошедших фильтр
    priced_specs = fetch_specs_with_prices(fetcher, series_id)
    config_specs = {}
    if not priced_specs:
        config_specs = fetch_series_config(fetcher, series_id)

    trims = []
    for spec_id, launch in fresh.items():
        info = priced_specs.get(spec_id) or config_specs.get(spec_id) or {}
        name = info.get("name") or ""
        if not name:
            continue
        trims.append(
            {
                "spec_id": spec_id,
                "name": name,
                "price_cny": info.get("price_cny"),
                "launch": launch,
            }
        )

    if not trims:
        return None

    trims.sort(key=lambda t: (t["price_cny"] is None, t["price_cny"] or 0))
    priced = [t["price_cny"] for t in trims if t["price_cny"]]

    return {
        "series_id": series_meta["series_id"],
        "name": series_meta["series_name"],
        "first_launch": min(f"{y:04d}.{m:02d}" for y, m in dates_found),
        "price_min_cny": min(priced) if priced else None,
        "price_max_cny": max(priced) if priced else None,
        "trims": trims,
    }


def build(args):
    now = datetime.now(timezone.utc)
    if args.reset:
        STATE_FILE.unlink(missing_ok=True)
        log.info("Состояние сброшено — обход начнётся заново")
    state = load_state()

    if not state.get("started_at"):
        state["started_at"] = now.isoformat()

    fetcher = Fetcher(delay_min=args.delay_min, delay_max=args.delay_max)
    deadline = time.time() + args.time_budget * 60

    # --- шаг 1: марки
    if state["brands"] is None:
        brands = fetch_brands(fetcher)
        if not brands:
            log.error("Не удалось получить список марок — выхожу")
            return 1
        if args.brands:
            wanted = {int(x) for x in args.brands.split(",")}
            brands = [b for b in brands if b["brand_id"] in wanted]
        if args.min_specs:
            brands = [b for b in brands if b["spec_count"] >= args.min_specs]
        state["brands"] = brands
        state["pending_brands"] = [b["brand_id"] for b in brands]
        save_state(state)

    brands_by_id = {b["brand_id"]: b for b in state["brands"]}
    log.info(
        "Марок к обработке: %s | моделей в очереди: %s",
        len(state["pending_brands"] or []),
        len(state["series_queue"]),
    )

    # --- шаг 2: страницы марок -> очередь моделей
    while state["pending_brands"]:
        if time.time() > deadline:
            log.info("Лимит времени на шаге марок — сохраняю прогресс")
            save_state(state)
            return finish(state, args, partial=True)

        brand_id = state["pending_brands"][0]
        brand = brands_by_id[brand_id]
        page = fetch_brand_page(fetcher, brand_id)

        for s in page["series"]:
            state["series_queue"].append(
                {
                    "brand_id": brand_id,
                    "brand_name": brand["name"],
                    "brand_latin": page["latin"],
                    "series_id": s["series_id"],
                    "series_name": s["name"],
                }
            )

        state["pending_brands"].pop(0)
        log.info(
            "Марка %s (%s): моделей %s | очередь %s | осталось марок %s",
            brand["name"], brand_id, len(page["series"]),
            len(state["series_queue"]), len(state["pending_brands"]),
        )
        save_state(state)

    # --- шаг 3: модели -> комплектации с фильтром по дате
    while state["series_queue"]:
        if time.time() > deadline:
            log.info("Лимит времени на шаге моделей — сохраняю прогресс")
            save_state(state)
            return finish(state, args, partial=True)

        meta = state["series_queue"][0]
        model = collect_series(fetcher, meta, args.years, now)
        state["stats"]["series_done"] += 1

        if model:
            key = str(meta["brand_id"])
            entry = state["collected"].setdefault(
                key,
                {
                    "brand_id": meta["brand_id"],
                    "brand": meta["brand_name"],
                    "brand_latin": meta["brand_latin"],
                    "models": [],
                },
            )
            entry["models"].append(model)
            state["stats"]["series_kept"] += 1
            log.info(
                "  + %s / %s — комплектаций %s (с %s)",
                meta["brand_name"], model["name"],
                len(model["trims"]), model["first_launch"],
            )

        state["series_queue"].pop(0)
        state["stats"]["requests"] = fetcher.requests_made
        if state["stats"]["series_done"] % 10 == 0:
            save_state(state)
            log.info(
                "Прогресс: обработано %s, оставлено %s, в очереди %s",
                state["stats"]["series_done"],
                state["stats"]["series_kept"],
                len(state["series_queue"]),
            )

    save_state(state)
    return finish(state, args, partial=False)


# ---------------------------------------------------------------- вывод

def finish(state, args, partial):
    brands_out = []
    for entry in state["collected"].values():
        models = sorted(entry["models"], key=lambda m: m["name"])
        if not models:
            continue
        brands_out.append(
            {
                "brand": entry["brand"],
                "brand_latin": entry.get("brand_latin"),
                "models": models,
            }
        )
    brands_out.sort(key=lambda b: b["brand"])

    total_models = sum(len(b["models"]) for b in brands_out)
    total_trims = sum(
        len(m["trims"]) for b in brands_out for m in b["models"]
    )

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "updated_at": updated_at,
        "source": "autohome.com.cn",
        "max_age_years": args.years,
        "complete": not partial,
        "counts": {
            "brands": len(brands_out),
            "models": total_models,
            "trims": total_trims,
        },
    }

    # --- полный файл (для отладки и как единый дамп)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    full_payload = enrich_full_dump({**meta, "brands": brands_out})
    OUTPUT_FILE.write_text(
        json.dumps(full_payload, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # --- двухуровневый вывод для фронтенда:
    #     index.json  — марки/модели/диапазоны цен (грузится сразу, лёгкий)
    #     specs/{id}.json — комплектации модели (грузится по выбору модели)
    specs_dir = OUTPUT_FILE.parent / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    for old in specs_dir.glob("*.json"):
        old.unlink()

    index_brands = []
    for b in brands_out:
        models_idx = []
        for m in b["models"]:
            models_idx.append(
                {
                    "id": m["series_id"],
                    "name": m["name"],
                    "launch": m["first_launch"],
                    "min": m["price_min_cny"],
                    "max": m["price_max_cny"],
                    "n": len(m["trims"]),
                }
            )
            spec_payload = enrich_spec_file(
                {
                    "id": m["series_id"],
                    "name": m["name"],
                    "brand": b["brand"],
                    "updated_at": updated_at,
                    "trims": m["trims"],
                }
            )
            (specs_dir / f"{m['series_id']}.json").write_text(
                json.dumps(spec_payload, ensure_ascii=False,
                           separators=(",", ":")),
                encoding="utf-8",
            )
        index_brands.append(
            {
                "brand": b["brand"],
                "latin": b.get("brand_latin"),
                "models": models_idx,
            }
        )

    index_file = OUTPUT_FILE.parent / "index.json"
    index_payload = enrich_index({**meta, "brands": index_brands})
    index_file.write_text(
        json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    index_kb = index_file.stat().st_size / 1024
    specs_kb = sum(f.stat().st_size for f in specs_dir.glob("*.json")) / 1024

    log.info("=" * 60)
    log.info(
        "%s: марок %s, моделей %s, комплектаций %s",
        "ЧАСТИЧНО (обход не завершён)" if partial else "ГОТОВО",
        len(brands_out), total_models, total_trims,
    )
    log.info("index.json: %.1f КБ (грузится калькулятором сразу)", index_kb)
    log.info("specs/: %s файлов, %.1f КБ суммарно (по требованию)",
             total_models, specs_kb)
    log.info("Полный дамп: %s (%.1f КБ)", OUTPUT_FILE, size_kb)
    log.info("Запросов выполнено: %s", state["stats"]["requests"])
    if partial:
        log.info("Запусти скрипт снова — обход продолжится с места остановки.")
    log.info("=" * 60)
    return 0


# ---------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(description="Парсер каталога autohome -> JSON")
    p.add_argument("--years", type=int, default=3,
                   help="максимальный возраст авто в годах (по умолчанию 3)")
    p.add_argument("--time-budget", type=int, default=300,
                   help="лимит времени в минутах (по умолчанию 300)")
    p.add_argument("--brands", type=str, default=None,
                   help="только эти brand_id через запятую (для тестов)")
    p.add_argument("--min-specs", type=int, default=0,
                   help="пропускать марки, у которых меньше N комплектаций")
    p.add_argument("--delay-min", type=float, default=1.2)
    p.add_argument("--delay-max", type=float, default=2.6)
    p.add_argument("--reset", action="store_true",
                   help="сбросить состояние и начать обход заново")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
