#!/usr/bin/env python3
"""
PalWorld Save File Parser for PST (PalWorld 1.0+ support)
"""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from urllib import request as url_request
from urllib.error import HTTPError

# ── Ensure vendored palsav is importable before any palsav imports ──────────
_VENDOR = Path(__file__).resolve().parent / "palsav"
if _VENDOR.is_dir():
    sys.path.insert(0, str(_VENDOR))

try:
    from palsav.json_tools import CustomEncoder
except ImportError:
    try:
        from palworld_save_tools.json_tools import CustomEncoder
    except ImportError:
        import uuid as _uuid
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, _uuid.UUID):
                    return str(obj)
                try:
                    return str(obj)
                except Exception:
                    return super().default(obj)

DECOMPRESS = None; GVAS_FILE = None; PAL_TYPES = None; CUSTOM_PROPS = None
_DEBUG = False  # set by --debug flag

def uid_guid_to_rest(guid_str):
    """Convert a GUID string like 'fd1c1f10-0000-0000-0000-000000000000'
    to the REST API decimal format (first 8 hex chars as int).
    This matches ShowPlayers/getPlayerUid convention used by PlayerSync."""
    hex_part = guid_str.replace("-", "")[:8]
    if hex_part:
        try:
            return str(int(hex_part, 16))
        except ValueError:
            pass
    return guid_str

def rest_to_save_filename(rest_uid):
    """Convert a REST decimal UID back to the GUID filename used for player saves.
    e.g. '4240498448' -> 'FD1C1F10000000000000000000000000'"""
    try:
        hex_str = format(int(rest_uid), '08X')
        return hex_str + "0" * 24
    except (ValueError, TypeError):
        return None


def import_parser():
    global DECOMPRESS, GVAS_FILE, PAL_TYPES, CUSTOM_PROPS
    attempts = [
        ("palsav.core", "decompress_sav_to_gvas", "palsav.gvas", "GvasFile",
         "palsav.paltypes", "PALWORLD_TYPE_HINTS", "PALWORLD_CUSTOM_PROPERTIES",
         "palsav (deafdudecomputers)"),
        ("palsav.palsav", "decompress_sav_to_gvas", "palsav.gvas", "GvasFile",
         "palsav.paltypes", "PALWORLD_TYPE_HINTS", "PALWORLD_CUSTOM_PROPERTIES",
         "palsav (bundled)"),
        ("palworld_save_tools.palsav", "decompress_sav_to_gvas",
         "palworld_save_tools.gvas", "GvasFile",
         "palworld_save_tools.paltypes", "PALWORLD_TYPE_HINTS", "PALWORLD_CUSTOM_PROPERTIES",
         "palworld-save-tools (cheahjs)"),
    ]
    for core_mod, core_fn, gvas_mod, gvas_cls, types_mod, th, tc, name in attempts:
        try:
            cm = __import__(core_mod, fromlist=[core_fn])
            gm = __import__(gvas_mod, fromlist=[gvas_cls])
            tm = __import__(types_mod, fromlist=[th, tc])
            global DECOMPRESS, GVAS_FILE, PAL_TYPES, CUSTOM_PROPS
            DECOMPRESS = getattr(cm, core_fn)
            GVAS_FILE = getattr(gm, gvas_cls)
            PAL_TYPES = getattr(tm, th)
            CUSTOM_PROPS = getattr(tm, tc)
            return name
        except (ImportError, AttributeError):
            continue
    return None

def find_level_sav(path):
    p = Path(path)
    if p.is_file() and p.name == "Level.sav":
        return str(p)
    if p.is_dir():
        for f in p.rglob("Level.sav"):
            return str(f)
    raise FileNotFoundError(f"Level.sav not found in {path}")

def decompress_sav(sav_path):
    with open(sav_path, "rb") as f:
        raw, _ = DECOMPRESS(f.read())
    gvas = GVAS_FILE.read(raw, PAL_TYPES, CUSTOM_PROPS) if hasattr(GVAS_FILE, "read") else GVAS_FILE().read(raw, PAL_TYPES, CUSTOM_PROPS)
    data = gvas.dump() if hasattr(gvas, "dump") else gvas.dumps()
    if isinstance(data, dict):
        return data
    return json.loads(data)

# ── Property helpers ─────────────────────────────────────────────────────────

def props_of(obj):
    """Unwrap properties/value from GVAS object.

    Older palsav libs used "properties" as the key for nested struct data.
    Newer palsav (deafdudecomputers) wraps struct data under "value" key
    (e.g. {"type":"StructProperty","value":{...}}).
    """
    if isinstance(obj, dict):
        return obj.get("properties") or obj.get("value") or obj
    return {}

def get_val(obj, *paths):
    """Navigate nested dict through path segments.
    If the final object is a StructProperty wrapper, unwrap its "value".
    """
    for path in paths:
        if not isinstance(obj, dict):
            return {}
        obj = obj.get(path, {})
    if isinstance(obj, dict) and "value" in obj and "type" in obj:
        return obj.get("value", {}) if isinstance(obj.get("value"), dict) else obj
    return obj if isinstance(obj, dict) else {}

def get_raw_val(obj, *paths):
    """Same as get_val but does NOT auto-unwrap StructProperty at the end.
    Useful when the raw GVAS property dicts (with type/value) are needed."""
    for path in paths:
        if not isinstance(obj, dict):
            return {}
        obj = obj.get(path, {})
    return obj if isinstance(obj, dict) else {}

def get_prop(d, key):
    """Get property.value from a dict property.
    Falls back to fuzzy match for snake_case vs PascalCase key differences.
    """
    v = d.get(key)
    if v is None:
        key_norm = key.lower().replace("_", "")
        for k in d:
            if k.lower().replace("_", "") == key_norm:
                v = d[k]
                break
    if isinstance(v, dict):
        v = v.get("value", v)
    return v

def prop_s(d, key, default=""):
    v = get_prop(d, key)
    return str(v) if v is not None else default

def prop_i(d, key, default=0):
    try: return int(get_prop(d, key))
    except: return default

# ── Main parse logic ─────────────────────────────────────────────────────────

def parse_players(data, container_cache):
    players = []
    ws = props_of(get_val(data, "properties", "worldSaveData"))

    char_map = ws.get("CharacterSaveParameterMap", {})
    if isinstance(char_map, dict):
        values = char_map.get("value", []) or char_map.get("values", [])
    else:
        values = char_map if isinstance(char_map, list) else []

    for entry in values:
        if not isinstance(entry, dict):
            continue

        # ── Extract player_uid from the map entry KEY (NOT from properties) ──
        # New palsav key is a struct: {"PlayerUId": {"value": "guid"}, "InstanceId": ..., "DebugName": ...}
        # Old palsav key is a plain guid string
        entry_key = entry.get("key") or entry.get("Key") or {}
        if isinstance(entry_key, dict):
            uid = prop_s(entry_key, "PlayerUId") or str(entry_key.get("value", ""))
            char_key = prop_s(entry_key, "InstanceId") or uid
        else:
            uid = str(entry_key)
            char_key = uid

        # Normalize UID to REST API decimal format to match PlayerSync convention
        uid = uid_guid_to_rest(uid)

        if not uid or uid in ("0", ""):
            continue

        # ── Extract player properties from the value ──
        value = entry.get("value") or entry.get("Value") or entry
        props = props_of(value)

        # Player properties live inside RawData.value.object after custom-property decode.
        # deafdudecomputers: RawData.value.object.SaveParameter.value
        # cheahjs:           RawData.value.SaveParameter.value.properties
        # OLD format:        props directly (no RawData)
        raw = get_val(props, "RawData", "value", "object", "SaveParameter", "value")
        if not raw:
            raw = get_val(props, "RawData", "value", "object")
        if not raw:
            raw = get_val(props, "RawData", "value", "SaveParameter", "value", "properties")
        if not raw:
            raw = props

        if _DEBUG and not raw:
            print(f"[DEBUG] All paths returned empty for entry {len(players)}", flush=True)
            rd = props.get("RawData", {})
            print(f"  RawData type: {rd.get('type', 'N/A')}", flush=True)
            rdv = rd.get("value", {})
            if isinstance(rdv, dict):
                print(f"  RawData.value keys: {sorted(rdv.keys())}", flush=True)
            else:
                print(f"  RawData.value = {type(rdv).__name__}", flush=True)

        if _DEBUG and not uid:
            print(f"[DEBUG] Entry {len(players)}:", flush=True)
            print(f"  char_key = {char_key!r}", flush=True)
            print(f"  props keys = {sorted(props.keys()) if isinstance(props, dict) else type(props).__name__}", flush=True)
            print(f"  raw keys = {sorted(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}", flush=True)
            if isinstance(raw, dict):
                for k, v in list(raw.items())[:5]:
                    sv = str(v)
                    if len(sv) > 120:
                        sv = sv[:120] + "..."
                    print(f"    {k} = {sv}", flush=True)

        if not uid or uid in ("0", ""):
            continue

        # ── Only count players (IsPlayer: True), skip wild pals / NPCs ──
        is_player = get_prop(raw, "IsPlayer")
        if not is_player or str(is_player) != "True":
            continue

        # ── Player found: build player dict ──
        player = {
            "player_uid": uid,
            "nickname": prop_s(raw, "nickname"),
            "level": prop_i(raw, "level"),
            "exp": prop_i(raw, "exp"),
            "hp": 0, "max_hp": 0,
            "max_status_point": 0, "status_point": {},
            "full_stomach": 0.0,
            "steam_id": prop_s(raw, "steam_id"),
            "user_id": prop_s(raw, "user_id"),
            "save_last_online": "",
            "pals": [],
            "items": None,
        }

        # Try to read HP from various property names
        hp_info = get_prop(raw, "HP")
        if isinstance(hp_info, dict):
            player["hp"] = prop_i(hp_info, "Value")
            player["max_hp"] = prop_i(hp_info, "MaxValue")

        # Status points
        status = get_prop(raw, "status_point") or get_prop(raw, "StatusPoint")
        if isinstance(status, dict):
            sp = {}
            for k, v in status.items():
                sp[k] = prop_i(v) if isinstance(v, dict) else int(v or 0)
            if sp:
                player["status_point"] = sp
                player["max_status_point"] = len(sp)

        # Full stomach
        stomach = get_prop(raw, "full_stomach") or get_prop(raw, "FullStomach")
        if isinstance(stomach, dict):
            player["full_stomach"] = float(stomach.get("value", 0) or 0)

        # Match pals from container cache (keyed by OwnerPlayerUId = player_uid)
        pals = container_cache.get(str(uid), [])
        if pals:
            player["pals"] = pals

        players.append(player)
    return players


def parse_containers(data):
    """Parse CharacterSaveParameterMap to extract pals grouped by owner player."""
    container_cache = {}
    ws = props_of(get_val(data, "properties", "worldSaveData"))

    char_map = ws.get("CharacterSaveParameterMap", {})
    if isinstance(char_map, dict):
        values = char_map.get("value", []) or char_map.get("values", [])
    else:
        values = char_map if isinstance(char_map, list) else []

    for entry in values:
        if not isinstance(entry, dict):
            continue

        value = entry.get("value") or entry.get("Value") or entry
        props = props_of(value)

        raw = get_val(props, "RawData", "value", "object", "SaveParameter", "value")
        if not raw:
            raw = get_val(props, "RawData", "value", "object")
        if not raw:
            raw = get_val(props, "RawData", "value", "SaveParameter", "value", "properties")
        if not raw:
            continue

        # Skip players — only extract pals (entries with OwnerPlayerUId)
        is_player = get_prop(raw, "IsPlayer")
        if is_player and str(is_player) == "True":
            continue

        owner_id = prop_s(raw, "OwnerPlayerUId")
        if not owner_id or owner_id == "00000000-0000-0000-0000-000000000000":
            continue
        owner_id = uid_guid_to_rest(owner_id)

        pal = {
            "type": prop_s(raw, "CharacterID"),
            "nickname": prop_s(raw, "NickName"),
            "gender": prop_s(raw, "Gender"),
            "level": prop_i(raw, "Level"),
            "rank": prop_i(raw, "Rank"),
            "exp": prop_i(raw, "Exp"),
            "hp": 0, "max_hp": 0,
            "melee": prop_i(raw, "MeleeAttack") or prop_i(raw, "Talent_Shot"),
            "ranged": prop_i(raw, "ShotAttack"),
            "defense": prop_i(raw, "Defense") or prop_i(raw, "Talent_Defense"),
            "workspeed": prop_i(raw, "CraftSpeed"),
            "is_lucky": str(get_prop(raw, "IsRarePal") or "") == "True",
            "is_boss": str(get_prop(raw, "IsBoss") or "") == "True",
            "is_tower": str(get_prop(raw, "IsTower") or "") == "True",
            "rank_attack": 0,
            "rank_defence": 0,
            "rank_craftspeed": 0,
            "skills": [],
        }

        # HP is FixedPoint64 struct: {Value: {value: int}}
        hp_info = get_prop(raw, "HP") or get_prop(raw, "Hp")
        if isinstance(hp_info, dict):
            pal["hp"] = prop_i(hp_info, "Value")
            pal["max_hp"] = prop_i(hp_info, "Value")

        if owner_id not in container_cache:
            container_cache[owner_id] = []
        container_cache[owner_id].append(pal)

    return container_cache


def parse_guilds(data, players):
    guilds = []
    ws = props_of(get_val(data, "properties", "worldSaveData"))

    group_map = ws.get("GroupSaveDataMap", {})
    if isinstance(group_map, dict):
        values = group_map.get("value", []) or group_map.get("values", [])
    else:
        values = group_map if isinstance(group_map, list) else []

    for entry in values:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value") or entry.get("Value") or entry
        props = props_of(value)

        # Guild properties live inside RawData.value after custom-property decode
        raw = get_val(props, "RawData", "value")
        if not raw:
            # Fallback: old format where props directly contain guild fields
            gt = prop_s(props, "group_type")
        else:
            gt = str(raw.get("group_type", ""))

        if "Guild" not in gt:
            continue

        if raw:
            gname = str(raw.get("group_name") or raw.get("guild_name") or "")
            admin = uid_guid_to_rest(str(raw.get("admin_player_uid") or ""))
            bcl = int(raw.get("base_camp_level") or 0)
        else:
            gname = prop_s(props, "group_name")
            admin = uid_guid_to_rest(prop_s(props, "admin_player_uid"))
            bcl = prop_i(props, "base_camp_level")

        guild_players = []
        if raw and "players" in raw:
            # New format: decoded guild has players list
            for gp_data in raw.get("players", []):
                if isinstance(gp_data, dict):
                    pid = uid_guid_to_rest(str(gp_data.get("player_uid", "")))
                    pname = ""
                    pi = gp_data.get("player_info", {})
                    if isinstance(pi, dict):
                        pname = str(pi.get("player_name", ""))
                    if not pname:
                        for p in players:
                            if p["player_uid"] == pid:
                                pname = p["nickname"]
                                break
                    guild_players.append({"player_uid": pid, "nickname": pname})
        else:
            # Old format: player_uid_list as ArrayProperty
            pids = get_prop(props, "player_uid_list")
            raw_ids = pids.get("values", []) if isinstance(pids, dict) else (pids if isinstance(pids, list) else [])
            for id_entry in raw_ids:
                pid = str(id_entry.get("value", "") if isinstance(id_entry, dict) else id_entry)
                if not pid:
                    continue
                pid = uid_guid_to_rest(pid)
                gp = {"player_uid": pid, "nickname": ""}
                for p in players:
                    if p["player_uid"] == pid:
                        gp["nickname"] = p["nickname"]
                        break
                guild_players.append(gp)

        guilds.append({
            "name": gname, "admin_player_uid": admin,
            "base_camp_level": bcl, "players": guild_players, "base_camp": [],
        })
    return guilds


def parse_player_saves(sav_path, players):
    """Parse individual player save files to extract inventory container GUIDs.
    Returns a dict mapping rest_uid -> {container_type_key: container_guid}"""
    sav_dir = Path(sav_path).parent
    players_dir = sav_dir / "Players"
    if not players_dir.is_dir():
        if _DEBUG:
            print(f"[DEBUG] Players directory not found: {players_dir}", flush=True)
        return {}

    uid_to_containers = {}
    for player in players:
        rest_uid = player.get("player_uid", "")
        filename = rest_to_save_filename(rest_uid)
        if not filename:
            continue
        save_file = players_dir / f"{filename}.sav"
        if not save_file.is_file():
            if _DEBUG:
                print(f"[DEBUG] Player save not found: {save_file}", flush=True)
            continue

        try:
            data = decompress_sav(str(save_file))
            props = props_of(data)
            save_data = get_val(props, "SaveData", "value")
            if not save_data:
                save_data = get_val(props, "SaveData")
            if not save_data:
                continue

            inv_info = save_data.get("InventoryInfo", {})
            if isinstance(inv_info, dict):
                inv_info = inv_info.get("value", inv_info)

            container_map = {}
            type_keys = [
                ("CommonContainerId", "CommonContainerId"),
                ("DropSlotContainerId", "DropSlotContainerId"),
                ("EssentialContainerId", "EssentialContainerId"),
                ("FoodEquipContainerId", "FoodEquipContainerId"),
                ("PlayerEquipArmorContainerId", "PlayerEquipArmorContainerId"),
                ("WeaponLoadOutContainerId", "WeaponLoadOutContainerId"),
            ]
            for json_key, _ in type_keys:
                cid_struct = inv_info.get(json_key, {})
                if isinstance(cid_struct, dict):
                    cid_struct = cid_struct.get("value", cid_struct) or cid_struct
                    cid_id = cid_struct.get("ID", {})
                    if isinstance(cid_id, dict):
                        cid_id = cid_id.get("value", cid_id)
                    container_map[json_key] = str(cid_id) if cid_id else None
                else:
                    container_map[json_key] = None

            uid_to_containers[rest_uid] = container_map
            if _DEBUG:
                found = sum(1 for v in container_map.values() if v and v != "00000000-0000-0000-0000-000000000000")
                print(f"[DEBUG] Player {rest_uid}: {found} inventory container(s) found", flush=True)
        except Exception as e:
            if _DEBUG:
                print(f"[DEBUG] Failed to parse player save {save_file}: {e}", flush=True)
            continue

    return uid_to_containers


def extract_slot_items(container_value):
    """Extract item list from a container's Slots array."""
    items = []
    slots = container_value.get("Slots", {})
    if isinstance(slots, dict):
        slot_values = slots.get("value", {})
        if isinstance(slot_values, dict):
            slot_values = slot_values.get("values", [])
        elif isinstance(slot_values, list):
            pass
        else:
            slot_values = []
    elif isinstance(slots, list):
        slot_values = slots
    else:
        return items

    for slot in (slot_values or []):
        if not isinstance(slot, dict):
            continue
        raw = slot.get("RawData", {})
        if isinstance(raw, dict):
            raw_val = raw.get("value", raw)
        else:
            raw_val = {}
        if not isinstance(raw_val, dict):
            continue
        slot_index = raw_val.get("slot_index", -1)
        count = raw_val.get("count", 0)
        item = raw_val.get("item", {})
        if isinstance(item, dict):
            static_id = item.get("static_id", "")
        else:
            static_id = ""
        if static_id and count:
            items.append({
                "SlotIndex": slot_index,
                "ItemId": static_id.lower(),
                "StackCount": count,
            })
    return items


def parse_items(data, players, sav_path=""):
    """Parse player inventory items by matching per-player container GUIDs
    against ItemContainerSaveData."""
    ws = props_of(get_val(data, "properties", "worldSaveData"))
    item_map = ws.get("ItemContainerSaveData", {})
    if isinstance(item_map, dict):
        containers = item_map.get("value", []) or item_map.get("values", [])
    else:
        containers = item_map if isinstance(item_map, list) else []

    container_items = {}
    for c in containers:
        if not isinstance(c, dict):
            continue
        cid_key = c.get("key", {}) or {}
        if isinstance(cid_key, dict):
            cid_id = cid_key.get("ID", {})
            if isinstance(cid_id, dict):
                cid = cid_id.get("value", "")
            else:
                cid = str(cid_id)
        else:
            cid = str(cid_key)

        cval = c.get("value", c) or {}
        if isinstance(cval, dict):
            cval = cval.get("value", cval) or cval

        items = extract_slot_items(cval)
        if cid and items:
            container_items[cid] = items

    if _DEBUG:
        print(f"[DEBUG] ItemContainerSaveData: {len(containers)} containers, {len(container_items)} with items", flush=True)

    uid_to_containers = parse_player_saves(sav_path, players)

    for player in players:
        rest_uid = player.get("player_uid", "")
        container_ids = uid_to_containers.get(rest_uid, {})

        items_dict = {}
        for json_key in [
            "CommonContainerId", "DropSlotContainerId", "EssentialContainerId",
            "FoodEquipContainerId", "PlayerEquipArmorContainerId", "WeaponLoadOutContainerId",
        ]:
            cid = container_ids.get(json_key)
            if cid and cid in container_items:
                items_dict[json_key] = container_items[cid]
            else:
                items_dict[json_key] = []

        has_items = any(v for v in items_dict.values())
        if has_items:
            player["items"] = items_dict
            if _DEBUG:
                total = sum(len(v) for v in items_dict.values())
                print(f"[DEBUG] Player {rest_uid}: {total} items in {sum(1 for v in items_dict.values() if v)} containers", flush=True)

    return players

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-f", "--file", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--debug", action="store_true", help="Save full GVAS JSON for debugging")
    args = p.parse_args()
    if args.debug:
        global _DEBUG
        _DEBUG = True
        os.environ["DEBUG"] = "1"

    src = import_parser()
    if not src:
        print("ERROR: No parser found. Install:", flush=True)
        print("  git clone https://github.com/deafdudecomputers/PalworldSaveTools.git", flush=True)
        print("  cd PalworldSaveTools && pip install -e src/palsav", flush=True)
        sys.exit(1)
    print(f"Parser: {src}", flush=True)

    sav = find_level_sav(args.file)
    print(f"File: {sav}", flush=True)

    try:
        data = decompress_sav(sav)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    if args.debug:
        dump_path = Path(sav).with_suffix(".json")
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=CustomEncoder, ensure_ascii=False, indent=2)
        print(f"Debug: saved GVAS JSON to {dump_path}", flush=True)

    containers = parse_containers(data)
    players = parse_players(data, containers)
    guilds = parse_guilds(data, players)
    players = parse_items(data, players, sav)
    print(f"Players: {len(players)}, with pals: {sum(1 for p in players if p['pals'])}, with items: {sum(1 for p in players if p.get('items'))}, Guilds: {len(guilds)}", flush=True)

    if _DEBUG and players:
        total_pals = sum(len(p.get("pals", [])) for p in players)
        print(f"[DEBUG] Total pals across all players: {total_pals}", flush=True)
        if total_pals > 0:
            sample = players[0]
            print(f"[DEBUG] First player: {sample['nickname']} ({sample['player_uid']})", flush=True)
            print(f"[DEBUG] Pals: {json.dumps(sample['pals'][:1], cls=CustomEncoder, ensure_ascii=False)}", flush=True)
            # Check if JSON serialization is valid for the full payload
            test_json = json.dumps(players, cls=CustomEncoder, ensure_ascii=False)
            print(f"[DEBUG] Full payload size: {len(test_json)} bytes", flush=True)

    base = args.request.rstrip("/")
    hdr = {"Content-Type": "application/json", "Authorization": f"Bearer {args.token}"}

    if players:
        try:
            req = url_request.Request(f"{base}/player", data=json.dumps(players).encode(), headers=hdr, method="PUT")
            with url_request.urlopen(req, timeout=30) as r:
                print(f"PUT /api/player → {r.status}", flush=True)
        except HTTPError as e:
            print(f"WARN: /api/player {e.code} {e.read().decode()[:200]}", flush=True)
        except Exception as e:
            print(f"WARN: /api/player {e}", flush=True)

    if guilds:
        try:
            req = url_request.Request(f"{base}/guild", data=json.dumps(guilds).encode(), headers=hdr, method="PUT")
            with url_request.urlopen(req, timeout=30) as r:
                print(f"PUT /api/guild → {r.status}", flush=True)
        except HTTPError as e:
            print(f"WARN: /api/guild {e.code} {e.read().decode()[:200]}", flush=True)
        except Exception as e:
            print(f"WARN: /api/guild {e}", flush=True)

    print("Done", flush=True)

if __name__ == "__main__":
    main()
