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

    # ── Toyota ──────────────────────────────────────────────────────────────
    "凯美瑞": "Camry", "卡罗拉": "Corolla", "雷凌": "Levin",
    "亚洲龙": "Avalon", "皇冠": "Crown", "皇冠陆放": "Crown Land Cruiser",
    "埃尔法": "Alphard", "威尔法": "Vellfire", "格瑞维亚": "Granvia",
    "赛那": "Sienna", "普拉多": "Prado", "兰德酷路泽": "Land Cruiser",
    "威兰达": "Venza", "威飒": "Wildlander", "凌尚": "Camry Sport",
    "锋兰达": "Frontlander", "卡罗拉锐放": "Corolla Cross",
    "铂智3X": "bZ3X", "铂智4X": "bZ4X", "铂智7": "bZ7",
    "丰田bZ3": "bZ3", "丰田bZ5": "bZ5",
    "RAV4荣放": "RAV4", "RAV4荣放双擎E+": "RAV4 PHEV",
    "T-ROC探歌": "T-ROC", "陆放": "Land Cruiser Prado",
    "海狮": "HiAce", "海狮Pro": "HiAce Pro",

    # ── Volkswagen ───────────────────────────────────────────────────────────
    "帕萨特": "Passat", "迈腾": "Magotan", "朗逸": "Lavida",
    "宝来": "Bora", "速腾": "Sagitar", "高尔夫": "Golf",
    "高尔夫GTI": "Golf GTI", "途观L": "Tiguan L",
    "途观L插电混动": "Tiguan L PHEV", "途岳": "Tharu",
    "探岳": "Tayron", "探岳X": "Tayron X", "探岳L PHEV": "Tayron L PHEV",
    "途昂": "Teramont", "途锐": "Touareg", "揽境": "Talagon",
    "揽巡": "Tayron GT", "凌渡": "Lamando", "威然": "Viloran",
    "途安": "Touran", "一汽-大众CC": "VW CC",
    "帕萨特插电混动": "Passat PHEV", "迈腾 PHEV": "Magotan PHEV",
    "大众ID.3": "ID.3", "与众06": "ID.6", "与众07": "Yuzhong 07",
    "与众08": "Yuzhong 08",

    # ── Honda ────────────────────────────────────────────────────────────────
    "雅阁": "Accord", "思域": "Civic", "奥德赛": "Odyssey",
    "艾力绅": "Elysion", "冠道": "Avancier", "皓影": "Breeze",
    "皓影新能源": "Breeze PHEV", "缤智": "Vezel",
    "英仕派": "Inspire", "英仕派新能源": "Inspire NEV",
    "型格": "Integra", "本田CR-V": "CR-V", "本田HR-V": "HR-V",
    "本田UR-V": "UR-V", "本田XR-V": "XR-V",
    "猎光e:NS2": "e:NS2", "东风本田S7": "Honda S7",
    "广汽本田P7": "Honda P7",

    # ── Nissan ───────────────────────────────────────────────────────────────
    "轩逸": "Sylphy", "天籁": "Teana", "奇骏": "X-Trail",
    "逍客": "Qashqai", "骐达TIIDA": "Tiida", "纳瓦拉": "Navara",
    "探陆": "Pathfinder", "日产N6": "Nissan N6", "日产N7": "Nissan N7",
    "日产NX8": "Nissan NX8",
    "锋坦Frontier Pro": "Frontier Pro", "锋坦Frontier Pro PHEV": "Frontier Pro PHEV",

    # ── Mazda ────────────────────────────────────────────────────────────────
    "马自达3 昂克赛拉": "Mazda 3 Axela", "马自达CX-30": "CX-30",
    "马自达CX-5": "CX-5", "马自达CX-50行也": "CX-50",
    "马自达EZ-6": "EZ-6", "马自达EZ-60": "EZ-60",

    # ── Hyundai ──────────────────────────────────────────────────────────────
    "伊兰特": "Elantra", "伊兰特Elantra N": "Elantra N",
    "途胜": "Tucson", "胜达": "Santa Fe", "索纳塔": "Sonata",
    "库斯途": "Custin", "帕里斯帝": "Palisade",
    "北京现代ix35": "ix35", "IONIQ 5 N(艾尼氪5N)": "IONIQ 5 N",
    "EO 羿欧": "IONIQ 6",

    # ── Kia ──────────────────────────────────────────────────────────────────
    "起亚K3": "K3", "起亚K5": "K5", "起亚EV5": "EV5", "起亚EV6": "EV6",
    "奕跑": "Stonic", "嘉华": "Carnival",
    "狮铂拓界": "Sportage", "索奈": "Sonet", "赛图斯": "Seltos",

    # ── Subaru ───────────────────────────────────────────────────────────────
    "森林人": "Forester", "傲虎": "Outback",
    "斯巴鲁BRZ": "BRZ", "斯巴鲁WRX": "WRX",

    # ── Lexus ────────────────────────────────────────────────────────────────
    "雷克萨斯ES": "ES", "雷克萨斯GX": "GX", "雷克萨斯IS": "IS",
    "雷克萨斯LC": "LC", "雷克萨斯LM": "LM", "雷克萨斯LS": "LS",
    "雷克萨斯LX": "LX", "雷克萨斯NX": "NX", "雷克萨斯NX新能源": "NX PHEV",
    "雷克萨斯RX": "RX", "雷克萨斯RX新能源": "RX PHEV", "雷克萨斯RZ": "RZ",
    "雷克萨斯UX": "UX",

    # ── BMW ──────────────────────────────────────────────────────────────────
    "宝马2系": "2 Series", "宝马2系(进口)": "2 Series (Import)",
    "宝马3系": "3 Series", "宝马4系": "4 Series",
    "宝马5系": "5 Series", "宝马5系(进口)": "5 Series (Import)",
    "宝马7系": "7 Series", "宝马M2": "M2", "宝马M235L": "M235L",
    "宝马M240i": "M240i", "宝马M3": "M3", "宝马M4": "M4",
    "宝马M5新能源": "M5 PHEV", "宝马M760Le": "M760Le",
    "宝马X1": "X1", "宝马X1 M35Li": "X1 M35Li",
    "宝马X2 M35i": "X2 M35i", "宝马X2(进口)": "X2 (Import)",
    "宝马X3": "X3", "宝马X3 M50": "X3 M50",
    "宝马X5": "X5", "宝马X6": "X6", "宝马X7": "X7",
    "宝马X7 M60i": "X7 M60i", "宝马XM": "XM",
    "宝马i3": "i3", "宝马i4": "i4", "宝马i4 M": "i4 M",
    "宝马i5": "i5", "宝马i5 M60": "i5 M60",
    "宝马i7": "i7", "宝马i7 M70L": "i7 M70L", "宝马iX1": "iX1",

    # ── Mercedes-Benz ────────────────────────────────────────────────────────
    "奔驰A级": "A-Class", "奔驰A级AMG": "A-Class AMG",
    "奔驰A级AMG(进口)": "A-Class AMG (Import)",
    "奔驰C级": "C-Class", "奔驰C级AMG": "C-Class AMG",
    "奔驰C级新能源": "C-Class PHEV", "奔驰C级AMG新能源": "C-Class AMG PHEV",
    "奔驰E级": "E-Class", "奔驰E级(进口)": "E-Class (Import)",
    "奔驰E级新能源": "E-Class PHEV",
    "奔驰S级": "S-Class", "奔驰S级新能源": "S-Class PHEV",
    "奔驰S级AMG新能源": "S-Class AMG PHEV",
    "奔驰G级": "G-Class", "奔驰G级AMG": "G-Class AMG",
    "奔驰G级新能源": "G-Class EV",
    "奔驰GLA": "GLA", "奔驰GLA AMG": "GLA AMG",
    "奔驰GLB": "GLB", "奔驰GLB AMG": "GLB AMG",
    "奔驰GLC": "GLC", "奔驰GLC AMG": "GLC AMG",
    "奔驰GLC新能源": "GLC PHEV", "奔驰GLC轿跑": "GLC Coupe",
    "奔驰GLC轿跑 AMG": "GLC Coupe AMG",
    "奔驰GLE(进口)": "GLE", "奔驰GLE AMG": "GLE AMG",
    "奔驰GLE新能源": "GLE PHEV", "奔驰GLE轿跑": "GLE Coupe",
    "奔驰GLE轿跑 AMG": "GLE Coupe AMG",
    "奔驰GLS": "GLS", "奔驰GLS AMG": "GLS AMG",
    "奔驰SL级AMG": "SL AMG",
    "奔驰CLA(进口)": "CLA", "奔驰CLA AMG": "CLA AMG",
    "奔驰CLA新能源": "CLA EV", "奔驰CLE": "CLE", "奔驰CLE AMG": "CLE AMG",
    "奔驰EQA": "EQA", "奔驰EQB": "EQB",
    "奔驰EQE": "EQE", "奔驰EQE SUV": "EQE SUV",
    "奔驰EQE SUV AMG": "EQE SUV AMG",
    "奔驰EQS": "EQS", "奔驰EQS SUV": "EQS SUV",
    "奔驰V级": "V-Class", "威霆": "Vito",
    "迈巴赫S级": "Maybach S-Class", "迈巴赫GLS": "Maybach GLS",
    "迈巴赫EQS SUV": "Maybach EQS SUV",

    # ── Audi ─────────────────────────────────────────────────────────────────
    "奥迪A3": "A3", "奥迪A4L": "A4L", "奥迪A4(进口)": "A4 (Import)",
    "奥迪A5(进口)": "A5 (Import)", "奥迪A5L": "A5L",
    "奥迪A5L Sportback": "A5L Sportback",
    "奥迪A6L": "A6L", "奥迪A6(进口)": "A6 (Import)",
    "奥迪A6L e-tron": "A6L e-tron",
    "奥迪A7": "A7", "奥迪A7L": "A7L",
    "奥迪A8": "A8",
    "奥迪Q2L": "Q2L", "奥迪Q3": "Q3",
    "奥迪Q4 e-tron": "Q4 e-tron", "奥迪Q5 e-tron": "Q5 e-tron",
    "奥迪Q5L": "Q5L", "奥迪Q5L Sportback": "Q5L Sportback",
    "奥迪Q6": "Q6", "奥迪Q6L e-tron": "Q6L e-tron",
    "奥迪Q6L Sportback e-tron": "Q6L Sportback e-tron",
    "奥迪Q7": "Q7", "奥迪Q8": "Q8",
    "奥迪RS 4": "RS 4", "奥迪RS 5": "RS 5", "奥迪RS 6": "RS 6",
    "奥迪RS 7": "RS 7", "奥迪RS Q8": "RS Q8",
    "奥迪S4": "S4", "奥迪S5": "S5", "奥迪S6": "S6",
    "奥迪S7": "S7", "奥迪S8": "S8",
    "奥迪SQ5": "SQ5", "奥迪SQ5 Sportback": "SQ5 Sportback",
    "奥迪SQ7": "SQ7", "奥迪SQ8": "SQ8",

    # ── Volvo ────────────────────────────────────────────────────────────────
    "沃尔沃S60": "S60", "沃尔沃S90": "S90",
    "沃尔沃S90插电式混动": "S90 PHEV",
    "沃尔沃V60": "V60", "沃尔沃V90": "V90",
    "沃尔沃XC40": "XC40", "沃尔沃XC60": "XC60",
    "沃尔沃XC60插电式混动": "XC60 PHEV",
    "沃尔沃XC70插电式混动": "XC70 PHEV",
    "沃尔沃XC90": "XC90", "沃尔沃XC90插电式混动": "XC90 PHEV",
    "沃尔沃EX30": "EX30", "沃尔沃EX90": "EX90",
    "沃尔沃EM90": "EM90", "沃尔沃ES90": "ES90",

    # ── Land Rover ───────────────────────────────────────────────────────────
    "揽胜": "Range Rover", "揽胜新能源": "Range Rover PHEV",
    "揽胜运动": "Range Rover Sport", "揽胜运动新能源": "Range Rover Sport PHEV",
    "揽胜星脉": "Range Rover Velar", "揽胜极光": "Range Rover Evoque",
    "发现": "Discovery", "路虎卫士": "Defender",

    # ── Ford ─────────────────────────────────────────────────────────────────
    "蒙迪欧": "Mondeo", "锐界": "Edge", "锐际": "Escape",
    "探险者": "Explorer", "全顺": "Transit", "E全顺": "E-Transit",
    "全顺T8": "Transit T8", "途睿欧": "Tourneo",
    "福特F-150猛禽": "F-150 Raptor", "游骑侠Ranger": "Ranger",
    "福特烈马": "Bronco", "福特智趣烈马": "Bronco Sport",
    "领睿": "Equator", "领睿新能源": "Equator PHEV",
    "领裕新能源": "Territory PHEV",

    # ── Cadillac / Buick ─────────────────────────────────────────────────────
    "凯迪拉克CT5": "CT5", "凯迪拉克CT6": "CT6",
    "凯迪拉克XT4": "XT4", "凯迪拉克XT5": "XT5", "凯迪拉克XT6": "XT6",
    "IQ锐歌": "LYRIQ", "IQ傲歌": "OPTIQ", "凯威德": "Escalade",
    "别克GL8": "GL8", "别克GL8新能源": "GL8 PHEV",
    "君威": "Regal", "君越": "LaCrosse",
    "昂科威Plus": "Envision Plus", "昂科威S": "Envision S",
    "微蓝6": "Velite 6", "别克E5": "Electra E5",
    "世纪": "Buick Century",
    "别克至境E7": "Electra E7", "别克至境L7": "Electra L7",
    "别克至境世家": "Electra Shijia",

    # ── Infiniti ─────────────────────────────────────────────────────────────
    "英菲尼迪QX50": "QX50", "英菲尼迪QX60": "QX60",
    "英菲尼迪QX80": "QX80",

    # ── Mitsubishi ───────────────────────────────────────────────────────────
    "帕杰罗": "Pajero", "欧蓝德": "Outlander",
    "奕歌": "Eclipse Cross", "劲炫": "ASX",
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
