import json, urllib.request, time, os
from pathlib import Path

PALS_DIR = Path(r'H:\Hermes Project\palworld-server-tool\web\src\assets\pals')
PAL_JSON = Path(r'H:\Hermes Project\palworld-server-tool\web\src\assets\pal.json')
ICON_URL = 'https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_{}_icon_normal.webp'

with open(PAL_JSON, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

en = data['en']

# Get all pal IDs (separate regular vs BOSS/GYM)
regular_pals = []
variant_pals = []

for pid in sorted(en.keys()):
    if pid.startswith(('BOSS_', 'GYM_', 'RAID_')):
        # Extract the base pal ID from variant
        base = pid
        for prefix in ['BOSS_', 'GYM_', 'RAID_']:
            if pid.startswith(prefix):
                base = pid[len(prefix):]
                break
        # Remove suffixes like _Dark, _2, _Avatar, _Servant
        import re
        base = re.sub(r'_(Dark|Ice|Fire|Water|Grass|Electric|Ground|Dragon|Neutral|2|Avatar|Servant)$', '', base)
        variant_pals.append((pid, base))
    elif not pid.startswith(('Arena_', 'Quest_', 'Believer_', 'Police_', 'Male_', 'Female_', 'baker_')):
        regular_pals.append(pid)

print(f"Regular pals: {len(regular_pals)}")
print(f"Boss/Gym variants: {len(variant_pals)}")

# Check what's missing
existing = {p.stem.lower() for p in PALS_DIR.glob('*.png')}
existing.update({p.stem.lower() for p in PALS_DIR.glob('*.webp')})

missing_regular = [p for p in regular_pals if p.lower() not in existing]
print(f"Missing regular icons: {len(missing_regular)}")

# Download missing icons
downloaded = 0
for i, pal_id in enumerate(missing_regular):
    url = ICON_URL.format(pal_id)
    save_path = PALS_DIR / f"{pal_id.lower()}.webp"
    print(f"[{i+1}/{len(missing_regular)}] {pal_id}...", end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            if r.status == 200 and len(data) > 100:
                with open(save_path, 'wb') as f:
                    f.write(data)
                # Also check if we need PNG version for BOSS/GYM
                downloaded += 1
                print(f"OK ({len(data)} bytes)")
            else:
                print(f"FAIL (status={r.status}, size={len(data)})")
    except Exception as e:
        print(f"FAIL ({e})")
    time.sleep(0.15)

print(f"\nDownloaded {downloaded} icons.")

# Now handle BOSS/GYM variants - copy from base pal if exists
for variant_id, base_id in variant_pals:
    variant_path = PALS_DIR / f"{variant_id.lower()}.png"
    base_path_webp = PALS_DIR / f"{base_id.lower()}.webp"
    base_path_png = PALS_DIR / f"{base_id.lower()}.png"
    
    if not variant_path.exists():
        for src in [base_path_webp, base_path_png]:
            if src.exists():
                import shutil
                shutil.copy2(src, variant_path)
                print(f"Copied: {variant_id.lower()}.png <- {src.name}")
                break
