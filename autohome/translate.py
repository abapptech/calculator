#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Перевод названий марок, моделей и комплектаций autohome на английский.

Три уровня:
  1) BRAND_EN / MODEL_EN — выверенные вручную соответствия для известных
     марок и моделей (маркетинговые названия: 海豹 -> Seal, а не Haibao)
  2) TERMS — словарь повторяющихся терминов комплектаций
     (豪华型 -> Luxury, 四驱 -> AWD, 纯电 -> Electric ...)
  3) pypinyin — транслитерация того, что осталось (редкие названия)

Запуск как скрипт добавляет поля *_en в уже собранные данные,
без повторного обхода сайта:
    python translate.py --data-dir data
"""

import argparse
import json
import re
from pathlib import Path

try:
    from pypinyin import lazy_pinyin
    HAS_PINYIN = True
except ImportError:  # транслитерация недоступна — останется оригинал
    HAS_PINYIN = False

CJK = re.compile(r"[\u4e00-\u9fff]")


# ---------------------------------------------------------------- марки

BRAND_EN = {
    # китайские бренды и суббренды
    "一汽": "FAW", "上汽跃进": "SAIC Yuejin", "东风": "Dongfeng",
    "东风奕派": "Dongfeng eπ", "东风富康": "Dongfeng Fukang",
    "东风小康": "Dongfeng Sokon", "东风御风": "Dongfeng Yufeng",
    "东风风光": "Dongfeng Fengon", "东风风度": "Dongfeng Fengdu",
    "东风风神": "Dongfeng Aeolus", "东风风行": "Dongfeng Forthing",
    "中兴": "ZX Auto", "中国重汽": "Sinotruk", "中通客车": "Zhongtong Bus",
    "乐道": "Onvo", "五十铃": "Isuzu", "五菱汽车": "Wuling",
    "享界": "Stelato", "仰望": "Yangwang", "依维柯": "Iveco",
    "凯翼": "Cowin", "凯马": "Kama", "创维汽车": "Skyworth Auto",
    "北京汽车": "BAIC", "北京汽车制造厂": "BAW", "北京越野": "BAIC Off-Road",
    "吉利几何": "Geely Geometry", "吉利汽车": "Geely",
    "吉利银河": "Geely Galaxy", "吉利雷达": "Geely Radar",
    "启辰": "Venucia", "哈弗": "Haval", "坦克": "Tank",
    "埃安": "AION", "大通": "Maxus", "大运": "Dayun",
    "奇瑞": "Chery", "奇瑞QQ": "Chery QQ", "奇瑞新能源": "Chery NEV",
    "奇瑞风云": "Chery Fulwin", "奔腾": "Bestune", "宇通客车": "Yutong Bus",
    "宝骏": "Baojun", "尊界": "Maextro", "小米汽车": "Xiaomi Auto",
    "小鹏": "XPeng", "尚界": "Shangjie", "岚图汽车": "Voyah",
    "广汽传祺": "GAC Trumpchi", "广汽昊铂": "GAC Hyptec",
    "开瑞": "Karry", "思皓": "Sehol", "捷途": "Jetour",
    "捷途山海": "Jetour Shanhai", "捷达": "Jetta", "方程豹": "Fangchengbao",
    "星途": "Exeed", "smart": "smart", "智己汽车": "IM Motors",
    "智界": "Luxeed", "极氪": "Zeekr", "欧拉": "ORA",
    "比亚迪": "BYD", "江汽集团": "JAC", "江淮汽车": "JAC",
    "江淮瑞风": "JAC Refine", "江淮钇为": "JAC Yiwei", "江铃": "JMC",
    "江铃集团新能源": "JMEV", "深蓝汽车": "Deepal", "灵悉": "Lingxi",
    "猛士": "M-Hero", "理想汽车": "Li Auto", "瑞驰汽车": "Ruichi",
    "睿蓝汽车": "Livan", "福田": "Foton", "红旗": "Hongqi",
    "腾势": "Denza", "荣威": "Roewe", "蓝电": "Landian",
    "蔚来": "NIO", "越界": "Yuejie", "远程": "Farizon",
    "金旅": "Golden Dragon", "金杯": "Jinbei", "金龙": "King Long",
    "鑫源汽车": "SRM Xinyuan", "长城": "Great Wall", "长安": "Changan",
    "长安凯程": "Changan Kaicene", "长安启源": "Changan Nevo",
    "长安欧尚": "Changan Oshan", "长安跨越": "Changan Kuayue",
    "阿维塔": "Avatr", "零跑汽车": "Leapmotor", "领克": "Lynk & Co",
    "领途汽车": "Lingtu", "飞碟汽车": "Feidie", "魏牌": "WEY",
    "黄海": "Huanghai", "名爵": "MG", "橙仕": "Chengshi",
    "知豆": "Zhidou", "云度": "Yudo", "菱势汽车": "Lingshi",
    "凌宝汽车": "Lingbao", "海马": "Haima", "曹操汽车": "Caocao Auto",
    "启境": "Qijing", "华境": "Huajing", "示界": "Shijie",
    "万象汽车": "Wanxiang", "九龙": "Joylong", "金冠汽车": "Jinguan",
    "成功汽车": "Chenggong", "国吉商用车": "Guoji", "SWM斯威汽车": "SWM",
    "AITO 问界": "AITO", "ARCFOX极狐": "ARCFOX", "Polestar极星": "Polestar",
    "ROX极石": "ROX", "firefly萤火虫": "firefly", "iCAR": "iCAR",
    "AM晓澳": "AM", "LIMGENE凌际": "LIMGENE", "AUXUN傲旋": "AUXUN",
    "Lorinser罗伦士": "Lorinser", "威麟": "Rely",

    # зарубежные
    "丰田": "Toyota", "保时捷": "Porsche", "兰博基尼": "Lamborghini",
    "凯迪拉克": "Cadillac", "别克": "Buick", "大众": "Volkswagen",
    "奔驰": "Mercedes-Benz", "奥迪": "Audi", "奥迪AUDI": "Audi",
    "宝马": "BMW", "宾利": "Bentley", "捷尼赛思": "Genesis",
    "捷豹": "Jaguar", "斯巴鲁": "Subaru", "日产": "Nissan",
    "本田": "Honda", "林肯": "Lincoln", "标致": "Peugeot",
    "沃尔沃": "Volvo", "法拉利": "Ferrari", "特斯拉": "Tesla",
    "玛莎拉蒂": "Maserati", "现代": "Hyundai", "福特": "Ford",
    "英力士掷弹兵": "Ineos Grenadier", "英菲尼迪": "Infiniti",
    "莲花跑车": "Lotus", "起亚": "Kia", "路虎": "Land Rover",
    "迈凯伦": "McLaren", "雪铁龙": "Citroen", "雷克萨斯": "Lexus",
    "马自达": "Mazda", "阿尔法·罗密欧": "Alfa Romeo",
    "阿斯顿·马丁": "Aston Martin", "卡尔森": "Carlsson",
    "迈莎锐": "Mansory", "克蒂汽车": "Kedi",
}


# ---------------------------------------------------------------- модели

# маркетинговые названия моделей — там, где транслитерация была бы неверной
MODEL_EN = {
    # BYD
    "汉": "Han", "唐": "Tang", "秦": "Qin", "宋": "Song", "元": "Yuan",
    "夏": "Xia", "海豹": "Seal", "海鸥": "Seagull", "海豚": "Dolphin",
    "海狮": "Sea Lion", "驱逐舰": "Destroyer", "护卫舰": "Frigate",
    "腾势": "Denza", "仰望": "Yangwang", "豹": "Bao",
    # Geely
    "帝豪": "Emgrand", "缤越": "Coolray", "缤瑞": "Bingrui",
    "星越": "Xingyue", "星瑞": "Xingrui", "博越": "Boyue",
    "星愿": "Starwish", "星舰": "Starship", "熊猫": "Panda",
    "银河": "Galaxy", "嘉际": "Jiaji", "豪越": "Haoyue",
    "远景": "Vision", "金刚": "Jingang",
    # Great Wall / WEY / ORA / Tank
    "蓝山": "Blue Mountain", "高山": "Gaoshan", "拿铁": "Latte",
    "摩卡": "Mocca", "玛奇朵": "Macchiato", "好猫": "Good Cat",
    "闪电猫": "Lightning Cat", "芭蕾猫": "Ballet Cat",
    "大狗": "Big Dog", "二代大狗": "Big Dog II", "猛龙": "Raptor",
    "枭龙": "Xiaolong", "赤兔": "Chitu", "神兽": "Shenshou",
    "炮": "Pao", "山海炮": "Shanhai Pao", "金刚炮": "Jingang Pao",
    # Chery / Exeed / Jetour
    "瑞虎": "Tiggo", "艾瑞泽": "Arrizo", "风云": "Fulwin",
    "瑶光": "Yaoguang", "星纪元": "Exlantix", "揽月": "Lanyue",
    "凌云": "Lingyun", "旅行者": "Traveller", "大圣": "Dashing",
    "山海": "Shanhai", "探索": "Explorer", "夏日": "Summer",
    # GAC / AION
    "影豹": "Empow", "影酷": "Emkoo", "传祺": "Trumpchi",
    "昊铂": "Hyptec", "霸王龙": "Tyrant", "绿静": "Lvjing",
    # Changan
    "逸动": "Eado", "锐程": "Raeton", "欧尚": "Oshan",
    "启源": "Nevo", "深蓝": "Deepal", "引力": "Gravity",
    "蓝鲸": "Bluewhale", "览拓者": "Lantuozhe", "猎手": "Hunter",
    "尚界": "Shangjie", "凯程": "Kaicene",
    # SAIC / Wuling / Baojun / Roewe / MG
    "宏光": "Hongguang", "缤果": "Bingo", "星光": "Starlight",
    "悦也": "Yep", "云朵": "Cloud", "云海": "Yunhai",
    "五菱之光": "Wuling Sunshine", "之光": "Sunshine", "荣光": "Rongguang",
    "扬光": "Yangguang", "征程": "Zhengcheng",
    # прочие популярные
    "问界": "AITO", "智界": "Luxeed", "享界": "Stelato",
    "尊界": "Maextro", "理想": "Li", "梦想家": "Dreamer",
    "追光": "Passion", "知音": "Zhiyin", "泰山": "Taishan",
    "极狐": "ARCFOX", "考拉": "Koala", "阿尔法": "Alpha",
    "宋": "Song", "唐L": "Tang L", "汉L": "Han L", "秦L": "Qin L",
    "元UP": "Yuan Up", "元PLUS": "Yuan Plus",
    "奕炫": "Yixuan", "奕派": "eπ", "皮卡": "Pickup",
    "小蚂蚁": "Little Ant", "冰淇淋": "Ice Cream",
    "宾理": "Binli", "睿蓝": "Livan", "枭龙MAX": "Xiaolong Max",
    "旗舰": "Flagship", "长安之星": "Changan Star",
    "神行者": "Shenxingzhe", "征服者": "Conqueror",
}


# ---------------------------------------------------------------- термины

# порядок важен: применяется от самых длинных к коротким
TERMS = {
    # тип силовой установки
    "插电式混合动力": "PHEV", "插电混动": "PHEV", "油电混动": "Hybrid",
    "增程式": "EREV", "增程": "EREV", "纯电动": "Electric", "纯电": "Electric",
    "混动": "Hybrid", "双擎": "Hybrid", "汽油": "Petrol", "柴油": "Diesel",
    "天然气": "CNG", "双燃料": "Bi-fuel", "燃料电池": "Fuel Cell",
    "氢燃料": "Hydrogen", "电动": "Electric",

    # привод и трансмиссия
    "两驱": "2WD", "四驱": "AWD", "后驱": "RWD", "前驱": "FWD",
    "全时四驱": "Full-time AWD", "分时四驱": "Part-time AWD",
    "手自一体": "Automatic", "手动挡": "Manual", "自动挡": "Automatic",
    "手动": "Manual", "自动": "Automatic", "双电机": "Dual Motor",
    "单电机": "Single Motor", "三电机": "Tri Motor",

    # уровни комплектации
    "豪华型": "Luxury", "豪华版": "Luxury", "豪华": "Luxury",
    "舒适型": "Comfort", "舒适版": "Comfort", "舒适": "Comfort",
    "精英型": "Elite", "精英版": "Elite",
    "尊享型": "Premium", "尊享版": "Premium",
    "尊贵型": "Deluxe", "尊贵版": "Deluxe",
    "旗舰型": "Flagship", "旗舰版": "Flagship",
    "标准型": "Standard", "标准版": "Standard",
    "先锋型": "Pioneer", "先锋版": "Pioneer",
    "时尚型": "Fashion", "时尚版": "Fashion",
    "进取型": "Progressive", "进取版": "Progressive",
    "领先型": "Leading", "领先版": "Leading",
    "卓越型": "Excellence", "卓越版": "Excellence",
    "至尊型": "Ultimate", "至尊版": "Ultimate",
    "智享版": "Smart", "智驾版": "ADAS", "智联版": "Connect",
    "性能版": "Performance", "运动版": "Sport", "运动型": "Sport",
    "荣耀版": "Honor", "冠军版": "Champion", "纪念版": "Anniversary",
    "定制版": "Custom", "限量版": "Limited", "特别版": "Special",
    "焕新版": "Refresh", "悦行版": "Comfort Drive", "全能者": "All-Rounder",
    "探索版": "Explorer", "商务版": "Business", "商旅": "Business",
    "基本型": "Base", "入门版": "Entry", "创世版": "Genesis Ed.",
    "科技版": "Tech", "都市版": "Urban", "越野版": "Off-Road",
    "长续航": "Long Range", "超长续航": "Extended Range",
    "标准续航": "Standard Range", "增强版": "Enhanced",
    "版本": "Ed.",
    # годовщины: составные варианты раньше общих
    "五周年纪念版": "5th Anniversary Ed.", "十周年纪念版": "10th Anniversary Ed.",
    "三周年纪念版": "3rd Anniversary Ed.", "两周年纪念版": "2nd Anniversary Ed.",
    "周年纪念版": "Anniversary Ed.", "周年庆": "Anniversary",
    "纪念版": "Anniversary Ed.", "周年": "Anniversary",
    "二代": "2nd Gen", "三代": "3rd Gen", "第二代": "2nd Gen",
    # китайские числительные (применяются последними, после составных терминов)
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",

    # кузов, места, коммерческий транспорт
    "厢式运输车": "Box Van", "厢式汽车": "Box Truck", "厢货": "Box Truck",
    "仓栅式运输车": "Stake Body", "仓栅": "Stake Body",
    "栏板汽车": "Flatbed", "栏板": "Flatbed", "自卸": "Dump",
    "载货": "Cargo", "运输车": "Transporter", "牵引车": "Tractor",
    "冷藏车": "Refrigerated", "环卫": "Sanitation",
    "单排双后轮": "Single Cab DRW", "单排": "Single Cab",
    "双排": "Double Cab", "后单胎": "SRW", "后双胎": "DRW",
    "米后单轮": "m SRW", "后单轮": "SRW", "后双轮": "DRW",
    "长轴高顶": "LWB High Roof", "长轴中顶": "LWB Mid Roof",
    "短轴中顶": "SWB Mid Roof", "短轴低顶": "SWB Low Roof",
    "长轴低顶": "LWB Low Roof", "短轴高顶": "SWB High Roof",
    "长轴距": "LWB", "短轴距": "SWB", "加长": "Extended",
    "轴距": "WB", "高顶": "High Roof", "中顶": "Mid Roof",
    "低顶": "Low Roof", "长轴": "LWB", "短轴": "SWB",
    "对开门": "Split Doors", "侧滑门": "Sliding Door",
    "非营运": "Non-commercial", "营运": "Commercial",
    "非空调": "No A/C", "空调": "A/C", "客车": "Bus",
    "房车": "Motorhome", "座": "-seat", "排": "-row",
    "版": " Ed.", "型": "",

    # техника и поставщики
    "宁德时代": "CATL", "宁德": "CATL", "弗迪": "FinDreams",
    "国轩": "Gotion", "亿纬": "EVE", "中创新航": "CALB",
    "磷酸铁锂": "LFP", "三元锂": "NMC", "刀片电池": "Blade Battery",
    "线激光雷达": "-line LiDAR", "激光雷达": "LiDAR",
    "辅助驾驶": "ADAS", "智驾": "ADAS", "智能": "Smart",
    "全景天窗": "Panoramic Roof", "天窗": "Sunroof",
    "运动套装": "Sport Package", "套装": "Package",
    "真皮": "Leather", "座椅": "Seats", "无框车门": "Frameless Doors",
    "空气悬架": "Air Suspension", "康明斯": "Cummins",
    "潍柴": "Weichai", "玉柴": "Yuchai", "云内": "Yunnei",
    "全柴": "Quanchai", "东安": "Dongan", "柳机": "Liuji",
    "锐劲": "Ruijin", "国VI": "China VI", "国六": "China VI",
    "长风": "Changfeng", "长安": "Changan", "长城": "Great Wall",
    "国V": "China V", "国五": "China V",

    # прочее
    "改款": "Facelift", "款": " MY", "度": " kWh", "米": "m",
    "两厢": "Hatchback", "三厢": "Sedan", "轿跑": "Coupe",
    "旅行版": "Wagon", "敞篷": "Convertible",
    "创始版": "Founder Ed.", "首发版": "Launch Ed.",
    "五门": "5-door", "三门": "3-door", "四门": "4-door",
    "国产": "Domestic", "进口": "Imported",
}


# ---------------------------------------------------------------- движок

def _pinyin(text):
    """Транслитерация оставшихся китайских символов."""
    if not HAS_PINYIN:
        return text

    def repl(match):
        syllables = lazy_pinyin(match.group(0))
        word = "".join(syllables)
        return " " + word.capitalize() + " "

    return re.sub(r"[\u4e00-\u9fff]+", repl, text)


def _tidy(text):
    """Чистит двойные пробелы и висящие разделители."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,)）])", r"\1", text)
    text = re.sub(r"([(（])\s+", r"\1", text)
    text = text.replace("（", " (").replace("）", ")")
    text = re.sub(r"(\d)\s+-", r"\1-", text)
    text = re.sub(r"\s+-(seat|line|row|door)", r"-\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -·,")


_TERMS_SORTED = sorted(TERMS.items(), key=lambda kv: -len(kv[0]))


def apply_terms(text):
    """Подставляет словарные термины, самые длинные — первыми."""
    for cn, en in _TERMS_SORTED:
        if cn in text:
            text = text.replace(cn, " " + en + " " if en else " ")
    return text


def translate_brand(name, latin=None):
    """Латинское имя с autohome приоритетнее — оно официальное."""
    if name in BRAND_EN:
        return BRAND_EN[name]
    if latin and latin.strip():
        return latin.strip()
    if not CJK.search(name):
        return name
    stripped = re.sub(r"(汽车|集团|新能源|商用车|客车|房车)$", "", name)
    if stripped in BRAND_EN:
        return BRAND_EN[stripped]
    return _tidy(_pinyin(name))


def translate_model(name, brand_en=None, brand_cn=None):
    """
    Названия моделей на autohome непоследовательны: часть содержит марку
    ("五菱宏光"), часть нет ("元PLUS"). Префикс марки отделяем и подставляем
    её английское имя, чтобы не получалось "WulingHongguang".
    """
    if not CJK.search(name):
        return name
    if name in MODEL_EN:
        return MODEL_EN[name]

    prefix = ""
    if brand_cn:
        for variant in (brand_cn, re.sub(r"(汽车|集团|新能源|商用车)$", "", brand_cn)):
            if variant and name.startswith(variant) and len(name) > len(variant):
                name = name[len(variant):]
                prefix = (brand_en or variant) + " "
                break

    if name in MODEL_EN:
        return _tidy(prefix + MODEL_EN[name])

    # модель вида "宋PLUS新能源" -> ищем известную основу
    for cn, en in sorted(MODEL_EN.items(), key=lambda kv: -len(kv[0])):
        if name.startswith(cn):
            rest = name[len(cn):]
            return _tidy(prefix + en + " " + _translate_rest(rest))

    return _tidy(prefix + _translate_rest(name))


def _translate_rest(text):
    if not text:
        return ""
    text = text.replace("新能源", " NEV")
    text = apply_terms(text)
    return _pinyin(text)


def translate_trim(name):
    if not CJK.search(name):
        return _tidy(name)
    text = apply_terms(name)
    return _tidy(_pinyin(text))


# ---------------------------------------------------------------- применение

def enrich_index(payload):
    for b in payload.get("brands", []):
        b_en = translate_brand(b.get("brand", ""), b.get("latin") or b.get("brand_latin"))
        b["brand_en"] = b_en
        for m in b.get("models", []):
            m["name_en"] = translate_model(m.get("name", ""), b_en, b.get("brand"))
    return payload


def enrich_spec_file(payload):
    brand_en = translate_brand(payload.get("brand", ""))
    payload["brand_en"] = brand_en
    payload["name_en"] = translate_model(
        payload.get("name", ""), brand_en, payload.get("brand")
    )
    for t in payload.get("trims", []):
        t["name_en"] = translate_trim(t.get("name", ""))
    return payload


def enrich_full_dump(payload):
    for b in payload.get("brands", []):
        b_en = translate_brand(b.get("brand", ""), b.get("brand_latin"))
        b["brand_en"] = b_en
        for m in b.get("models", []):
            m["name_en"] = translate_model(m.get("name", ""), b_en, b.get("brand"))
            for t in m.get("trims", []):
                t["name_en"] = translate_trim(t.get("name", ""))
    return payload


def main():
    ap = argparse.ArgumentParser(
        description="Добавляет английские названия в собранные данные"
    )
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    data = Path(args.data_dir)
    if not HAS_PINYIN:
        print("ВНИМАНИЕ: pypinyin не установлен — редкие названия останутся "
              "на китайском. Установи: pip install pypinyin")

    index = data / "index.json"
    if index.exists():
        payload = json.loads(index.read_text(encoding="utf-8"))
        enrich_index(payload)
        index.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"index.json: марок {len(payload.get('brands', []))}")

    full = data / "autohome_prices.json"
    if full.exists():
        payload = json.loads(full.read_text(encoding="utf-8"))
        enrich_full_dump(payload)
        full.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print("autohome_prices.json: обновлён")

    specs = data / "specs"
    count = 0
    if specs.exists():
        for f in specs.glob("*.json"):
            payload = json.loads(f.read_text(encoding="utf-8"))
            enrich_spec_file(payload)
            f.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            count += 1
    print(f"specs/: обновлено файлов {count}")


if __name__ == "__main__":
    main()
