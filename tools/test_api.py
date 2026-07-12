import urllib.request, re, json

req = urllib.request.Request('https://paldb.cn/pals',
    headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode('utf-8')

# paldb.cn renders cards with: <a href="/pals/PAL_ID">...<img ... T_GAME_ID_icon... />...TEXT...</a>
# The GAME_ID in the image URL is what we need as key
# The text inside the card (first Chinese phrase) is the name

# Method: find all cards, match image game ID to card's Chinese text
cards = re.findall(
    r'<a href="/pals/([^"]+)"[^>]*>(.*?)</a>',
    html, re.DOTALL
)
print(f"Raw cards: {len(cards)}")

pal_map = {}
for pal_id, card in cards:
    # Find game ID from image URL in this card
    img_matches = re.findall(r'T_([A-Za-z_0-9]+)_icon_normal\.webp', card)
    if not img_matches:
        continue
    
    game_id = img_matches[0]
    
    # Find Chinese text inside the card
    cn_texts = re.findall(r'[\u4e00-\u9fff]{2,}', card)
    
    if cn_texts:
        # The pal name is usually the first or second CN text
        # (the first might be a label like "坐骑" or "工作适应性")
        name = cn_texts[0]
        # If the first CN text is very short (<3 chars) and there are more, use the next
        if len(name) < 3 and len(cn_texts) > 1:
            name = cn_texts[1]
        pal_map[game_id] = name

print(f"\nExtracted {len(pal_map)} pal names from paldb.cn")
for k, v in list(pal_map.items())[:20]:
    print(f"  {k}: {v}")

# Also handle search by checking the entire page for more data
# Some data might be in RSC payloads that we missed

# Search for T_ patterns near Chinese text in the full raw HTML
img_positions = list(re.finditer(r'T_([A-Za-z_0-9]+)_icon_normal\.webp', html))
print(f"\nTotal T_ image matches: {len(img_positions)}")

for m in img_positions:
    game_id = m.group(1)
    if game_id in pal_map:
        continue
    
    # Look ahead 3000 chars for Chinese text
    after = html[m.end():m.end()+3000]
    cn = re.findall(r'[\u4e00-\u9fff]{2,}', after)
    if cn:
        pal_map[game_id] = cn[0]

print(f"After full-page scan: {len(pal_map)} pal names")

# Save mapping
with open('pal_cn_from_paldb_cn.json', 'w', encoding='utf-8') as f:
    json.dump(pal_map, f, ensure_ascii=False, indent=2)

# Update pal.json with any missing/better translations
proj_path = r'H:\Hermes Project\palworld-server-tool'
with open(f'{proj_path}/web/src/assets/pal.json', 'r', encoding='utf-8-sig') as f:
    pal_data = json.load(f)

en = pal_data['en']
zh = pal_data['zh']

fixed = 0
improved = 0
for pid in sorted(en.keys()):
    if pid in pal_map:
        cn_name = pal_map[pid]
        old_zh = zh.get(pid, '')
        
        # Replace if zh is missing or is a placeholder
        is_bad = (
            not old_zh or
            old_zh == pid or
            re.match(r'^[A-Z][a-z]+\(BOSS\)$', old_zh) or
            re.match(r'^[A-Z_]+$', old_zh)
        )
        if is_bad:
            zh[pid] = cn_name
            fixed += 1
        elif old_zh != cn_name:
            # Prefer the paldb.cn name if it's different (might be more accurate)
            zh[pid] = cn_name
            improved += 1
            print(f"  IMPROVED: {pid}: {old_zh} -> {cn_name}")

# Save
with open(f'{proj_path}/web/src/assets/pal.json', 'w', encoding='utf-8') as f:
    json.dump(pal_data, f, ensure_ascii=False, indent=4)
    f.write('\n')

print(f"\nFixed: {fixed}, Improved: {improved}")
print("pal.json saved!")
