"""
PST 物品翻译补全脚本
将存档中未匹配的 static_id 映射到中文名并生成 items.json 补丁
"""

import json
import os
import sys

# 存档 static_id -> {zh_name, en_name, description_zh, description_en, key}
# key 用于在现有 items.json 中查找同类物品继承属性
MISSING_ITEMS = {
    # ── 基础素材 ──
    "Bio_Battery": {
        "id": "bio_battery",
        "name": "Bio Battery",
        "zh_name": "生化电池",
        "desc": "A device that converts bio-energy into electricity for storage.",
        "zh_desc": "可将生物能源转化为电力并存储的装置。用于驱动需要较高能量密度的机器。",
        "key": "BioBattery",
    },
    "Bio_Coolant": {
        "id": "bio_coolant",
        "name": "Bio Coolant",
        "zh_name": "极低温冷却介质",
        "desc": "High-efficiency cooling medium made from special Pal extracts.",
        "zh_desc": "用帕鲁身上提取的特殊成分制作的高效冷却介质。用于控制大功率设备的温度。",
        "key": "BioCoolant",
    },
    "Corrosive_Solvent": {
        "id": "corrosive_solvent",
        "name": "Corrosive Solvent",
        "zh_name": "腐蚀溶剂",
        "desc": "A dangerous chemical solvent with strong decomposition effects.",
        "zh_desc": "具有强效分解作用的危险化学溶剂，用于精密加工及特殊处理。",
        "key": "CorrosiveSolvent",
    },
    "Processed_Wood": {
        "id": "processed_wood",
        "name": "Processed Wood",
        "zh_name": "优质木板",
        "desc": "Carefully cut wooden board with beautiful grain.",
        "zh_desc": "精心切割硬木材得到的板材，拥有美丽的木纹。",
        "key": "ProcessedWood",
    },
    "Wood_Ancient": {
        "id": "wood_ancient",
        "name": "Ancient Mysterious Wood",
        "zh_name": "神秘木材",
        "desc": "Rare wood containing the power of the World Tree.",
        "zh_desc": "含有世界树力量的稀有木材。如果不是技术熟练的工匠甚至无法加工它。",
        "key": "AncientWood",
    },
    "Wood_Fine": {
        "id": "wood_fine",
        "name": "Fine Wood",
        "zh_name": "硬木材",
        "desc": "Carefully selected quality wood from trees in extreme environments.",
        "zh_desc": "精挑细选的优质木材。砍伐生长在沙漠、火山、雪山等极端环境下的树木可以获得。",
        "key": "FineWood",
    },
    "Cake03": {
        "id": "cake03",
        "name": "Cake (Tier 3)",
        "zh_name": "蛋糕(Lv.3)",
        "desc": "A delicious cake for breeding Pals.",
        "zh_desc": "用于帕鲁配种的美味蛋糕。",
        "key": "Cake03",
    },
    "KeySphere_01": {
        "id": "keysphere_01",
        "name": "Key Sphere 1",
        "zh_name": "钥匙球1",
        "desc": "A sphere key used to unlock certain chests.",
        "zh_desc": "用于开启特定宝箱的球型钥匙。",
        "key": "KeySphere01",
    },
    "KeySphere_02": {
        "id": "keysphere_02",
        "name": "Key Sphere 2",
        "zh_name": "钥匙球2",
        "desc": "A sphere key used to unlock certain chests.",
        "zh_desc": "用于开启特定宝箱的球型钥匙。",
        "key": "KeySphere02",
    },
    "KeySphere_03": {
        "id": "keysphere_03",
        "name": "Key Sphere 3",
        "zh_name": "钥匙球3",
        "desc": "A sphere key used to unlock certain chests.",
        "zh_desc": "用于开启特定宝箱的球型钥匙。",
        "key": "KeySphere03",
    },
    "KeySphere_04": {
        "id": "keysphere_04",
        "name": "Key Sphere 4",
        "zh_name": "钥匙球4",
        "desc": "A sphere key used to unlock certain chests.",
        "zh_desc": "用于开启特定宝箱的球型钥匙。",
        "key": "KeySphere04",
    },

    # ── 天坠之地 (Sky Island / 1.0) ──
    "SkyAssaultRifleBullet": {
        "id": "skyassaultriflebullet",
        "name": "Sky Assault Rifle Bullet",
        "zh_name": "天坠突击步枪子弹",
        "desc": "Ammunition for the Sky Assault Rifle.",
        "zh_desc": "天坠突击步枪的弹药。",
        "key": "SkyAssaultRifleBullet",
    },
    "SkyBowArrow": {
        "id": "skybowarrow",
        "name": "Sky Bow Arrow",
        "zh_name": "天坠弓箭",
        "desc": "Arrows for the Sky Bow.",
        "zh_desc": "天坠弓的箭矢。",
        "key": "SkyBowArrow",
    },
    "SkyGrenadeLauncherBullet": {
        "id": "skygrenadelauncherbullet",
        "name": "Sky Grenade Launcher Bullet",
        "zh_name": "天坠榴弹发射器子弹",
        "desc": "Ammunition for the Sky Grenade Launcher.",
        "zh_desc": "天坠榴弹发射器的弹药。",
        "key": "SkyGrenadeLauncherBullet",
    },
    "SkyShotgunBullet": {
        "id": "skyshotgunbullet",
        "name": "Sky Shotgun Bullet",
        "zh_name": "天坠霰弹枪子弹",
        "desc": "Ammunition for the Sky Shotgun.",
        "zh_desc": "天坠霰弹枪的弹药。",
        "key": "SkyShotgunBullet",
    },
    "SkySubmachineGunBullet": {
        "id": "skysubmachinegunbullet",
        "name": "Sky Submachine Gun Bullet",
        "zh_name": "天坠冲锋枪子弹",
        "desc": "Ammunition for the Sky Submachine Gun.",
        "zh_desc": "天坠冲锋枪的弹药。",
        "key": "SkySubmachineGunBullet",
    },
    "SkyIslandOre": {
        "id": "skyislandore",
        "name": "Sky Island Ore",
        "zh_name": "天坠矿石",
        "desc": "A rare ore found only on Sky Islands.",
        "zh_desc": "只能在天坠之地发现的珍贵矿石。",
        "key": "SkyIslandOre",
    },

    # ── 古代帕鲁球 ──
    "PalSphere_Ancient_1": {
        "id": "palsphere_ancient_1",
        "name": "Ancient Pal Sphere",
        "zh_name": "古代帕鲁球",
        "desc": "An ancient sphere for capturing Pals.",
        "zh_desc": "用于捕获帕鲁的古代球体。",
        "key": "AncientPalSphere",
    },
    "PalSphere_Ancient_2": {
        "id": "palsphere_ancient_2",
        "name": "Ancient Pal Sphere (Enhanced)",
        "zh_name": "古代帕鲁球(强化)",
        "desc": "An enhanced ancient sphere for capturing Pals.",
        "zh_desc": "用于捕获帕鲁的强化古代球体。",
        "key": "AncientPalSphere2",
    },

    # ── 突变帕鲁蛋 ──
    "PalEgg_MutationPal_05": {
        "id": "palegg_mutationpal_05",
        "name": "Huge Mutated Egg",
        "zh_name": "巨大突变帕鲁蛋",
        "desc": "A huge mutated Pal egg with a strange aura.",
        "zh_desc": "发生了非常罕见的特殊变异的巨大帕鲁蛋。",
        "key": "MutatedEgg05",
    },

    # ── 技能果实/卡片 ──
    "SkillCard_BubbleShower": {
        "id": "skillcard_bubbleshower",
        "name": "Skill Card: Bubble Shower",
        "zh_name": "技能果实:泡沫射击",
        "desc": "A skill fruit that teaches Bubble Shower.",
        "zh_desc": "能学会泡沫射击的技能果实。",
        "key": "SkillBubbleShower",
    },
    "PalPassiveSkillChange_Consumable_PAL_FullStomach_Down_3": {
        "id": "palpassiveskillchange_consumable_pal_fullstomach_down_3",
        "name": "Passive Skill Change: Full Stomach Down 3",
        "zh_name": "被动技能变更:饱腹度下降3",
        "desc": "A consumable that changes Pal passive skill to reduce hunger.",
        "zh_desc": "变更帕鲁被动技能为减少饱腹度下降的消耗品。",
        "key": "PassiveFullStomachDown3",
    },
    "WorkSuitability_AddTicket_MonsterFarm": {
        "id": "worksuitability_addticket_monsterfarm",
        "name": "Work Suitability Ticket: Monster Farm",
        "zh_name": "工作适应性券:牧场",
        "desc": "A ticket that adds Monster Farm work suitability to a Pal.",
        "zh_desc": "可赋予帕鲁牧场工作适应性的券。",
        "key": "WorkTicketMonsterFarm",
    },

    # ── 蓝图 (Blueprints) ── 使用基类武器名称 + "设计图"后缀
}

# 蓝图后缀规则: Blueprint_{Weapon}_{Tier} -> {WeaponName} 设计图 Lv.{Tier}
BLUEPRINT_MAP = {
    "Accessory_AT_1_2": ("攻击饰品设计图 Lv.2", "Attack Accessory Blueprint Lv.2", "AccessoryAT12"),
    "Accessory_ColdIce_1": ("冰结饰品设计图 Lv.1", "Cold Ice Accessory Blueprint Lv.1", "AccessoryColdIce1"),
    "Accessory_DFHP_1": ("防御HP饰品设计图 Lv.1", "Defense HP Accessory Blueprint Lv.1", "AccessoryDFHP1"),
    "Accessory_DragonResist_1_2": ("龙抗饰品设计图 Lv.2", "Dragon Resist Accessory Blueprint Lv.2", "AccessoryDragonResist12"),
    "Accessory_HP_1_2": ("HP饰品设计图 Lv.2", "HP Accessory Blueprint Lv.2", "AccessoryHP12"),
    "Accessory_HeatFire_1": ("火焰饰品设计图 Lv.1", "Fire Accessory Blueprint Lv.1", "AccessoryHeatFire1"),
    "Accessory_HeatResist_1_2": ("耐热饰品设计图 Lv.2", "Heat Resist Accessory Blueprint Lv.2", "AccessoryHeatResist12"),
    "Accessory_IceResist_1_2": ("耐寒饰品设计图 Lv.2", "Ice Resist Accessory Blueprint Lv.2", "AccessoryIceResist12"),
    "Accessory_LeafResist_1_2": ("耐草饰品设计图 Lv.2", "Leaf Resist Accessory Blueprint Lv.2", "AccessoryLeafResist12"),
    "Accessory_PPAT_1": ("攻击饰品设计图 Lv.1", "Attack Accessory Blueprint Lv.1", "AccessoryPPAT1"),
    "Accessory_PPDF_1": ("防御饰品设计图 Lv.1", "Defense Accessory Blueprint Lv.1", "AccessoryPPDF1"),
    "AncientArmor_2": ("古代防具设计图 Lv.2", "Ancient Armor Blueprint Lv.2", "AncientArmor2"),
    "AncientHelmet_2": ("古代头盔设计图 Lv.2", "Ancient Helmet Blueprint Lv.2", "AncientHelmet2"),
    "AncientHelmet_3": ("古代头盔设计图 Lv.3", "Ancient Helmet Blueprint Lv.3", "AncientHelmet3"),
    "AncientHelmet_5": ("古代头盔设计图 Lv.5", "Ancient Helmet Blueprint Lv.5", "AncientHelmet5"),
    "Bat3_4": ("棒球棍设计图 Lv.4", "Bat Blueprint Lv.4", "Bat34"),
    "BeamLauncher_3": ("光束发射器设计图 Lv.3", "Beam Launcher Blueprint Lv.3", "BeamLauncher3"),
    "BeamSword_4": ("光束剑设计图 Lv.4", "Beam Sword Blueprint Lv.4", "BeamSword4"),
    "Otomo_ATElectricity_ElementBoost_1": ("雷属性帕鲁增幅器设计图 Lv.1", "Electric Pal Boost Accessory Blueprint Lv.1", "OtomoATElec1"),
    "Otomo_ElementBoost_Dark_1_2": ("暗属性帕鲁增幅器设计图 Lv.2", "Dark Pal Boost Accessory Blueprint Lv.2", "OtomoDark12"),
    "Otomo_ElementBoost_Dragon_1_2": ("龙属性帕鲁增幅器设计图 Lv.2", "Dragon Pal Boost Accessory Blueprint Lv.2", "OtomoDragon12"),
    "Otomo_ElementBoost_Earth_1_2": ("地属性帕鲁增幅器设计图 Lv.2", "Earth Pal Boost Accessory Blueprint Lv.2", "OtomoEarth12"),
    "Otomo_ElementBoost_Electricity_1_2": ("雷属性帕鲁增幅器设计图 Lv.2", "Electric Pal Boost Accessory Blueprint Lv.2", "OtomoElec12"),
    "Otomo_ElementBoost_Ice_1_2": ("冰属性帕鲁增幅器设计图 Lv.2", "Ice Pal Boost Accessory Blueprint Lv.2", "OtomoIce12"),
    "SkyAssaultRifle_3": ("天坠突击步枪设计图 Lv.3", "Sky Assault Rifle Blueprint Lv.3", "SkyAssaultRifle3"),
    "SkyBeamSword_4": ("天坠光束剑设计图 Lv.4", "Sky Beam Sword Blueprint Lv.4", "SkyBeamSword4"),
    "SkyBow_2": ("天坠弓设计图 Lv.2", "Sky Bow Blueprint Lv.2", "SkyBow2"),
    "SkyBow_3": ("天坠弓设计图 Lv.3", "Sky Bow Blueprint Lv.3", "SkyBow3"),
    "SkyBow_5": ("天坠弓设计图 Lv.5", "Sky Bow Blueprint Lv.5", "SkyBow5"),
    "SkyShotgun_2": ("天坠霰弹枪设计图 Lv.2", "Sky Shotgun Blueprint Lv.2", "SkyShotgun2"),
    "SkySubmachineGun_2": ("天坠冲锋枪设计图 Lv.2", "Sky Submachine Gun Blueprint Lv.2", "SkySMG2"),
    "SkySubmachineGun_3": ("天坠冲锋枪设计图 Lv.3", "Sky Submachine Gun Blueprint Lv.3", "SkySMG3"),
    "SkySubmachineGun_4": ("天坠冲锋枪设计图 Lv.4", "Sky Submachine Gun Blueprint Lv.4", "SkySMG4"),
    "Sword_2": ("剑设计图 Lv.2", "Sword Blueprint Lv.2", "Sword2"),
    "Sword_3": ("剑设计图 Lv.3", "Sword Blueprint Lv.3", "Sword3"),
    "Sword_4": ("剑设计图 Lv.4", "Sword Blueprint Lv.4", "Sword4"),
    "WidePenetrateShotgun_3": ("穿透霰弹枪设计图 Lv.3", "Penetrate Shotgun Blueprint Lv.3", "WPSG3"),
}

# 将蓝图条目加入 MISSING_ITEMS
for bp_key, (zh_name, en_name, key) in BLUEPRINT_MAP.items():
    bp_id = f"blueprint_{bp_key.lower()}"
    MISSING_ITEMS[bp_id] = {
        "id": bp_id,
        "name": en_name,
        "zh_name": zh_name,
        "desc": f"A design blueprint for {en_name.lower().replace(' blueprint', '')}.",
        "zh_desc": f"{zh_name}，可用于制作对应装备。",
        "key": key,
    }


def main():
    items_json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "src", "assets", "items.json"
    )

    with open(items_json_path, "r", encoding="utf-8") as f:
        items_data = json.load(f)

    existing_ids = {item["id"] for item in items_data["en"]}
    existing_ids |= {item["id"] for item in items_data.get("zh", [])}

    new_count = 0
    for archive_id, info in MISSING_ITEMS.items():
        item_id = info["id"]
        if item_id in existing_ids:
            continue

        en_entry = {
            "id": item_id,
            "name": info["name"],
            "description": info["desc"],
            "key": info["key"],
        }
        zh_entry = {
            "id": item_id,
            "name": info["zh_name"],
            "description": info["zh_desc"],
            "key": info["key"],
        }
        ja_entry = {
            "id": item_id,
            "name": info["zh_name"],
            "description": info["zh_desc"],
            "key": info["key"],
        }

        items_data["en"].append(en_entry)
        items_data["zh"].append(zh_entry)
        if "ja" in items_data:
            items_data["ja"].append(ja_entry)

        new_count += 1
        print(f"  + {item_id} -> {info['zh_name']}")

    with open(items_json_path, "w", encoding="utf-8") as f:
        json.dump(items_data, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Added {new_count} new items to items.json")
    print(f"Total entries: en={len(items_data['en'])}, zh={len(items_data['zh'])}")


if __name__ == "__main__":
    main()
