import json, re

with open(r'H:\Hermes Project\palworld-server-tool\web\src\assets\pal.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

zh = data['zh']
tests = ['PandaGirl', 'LotusDragon', 'BlackPuppy_Ice', 'Sekhmet']
for t in tests:
    name = zh.get(t, 'NOT FOUND')
    print(f'{t}: {name}')
    # Verify it has Chinese chars
    has_cn = bool(re.search(r'[\u4e00-\u9fff]', name))
    print(f'  has Chinese: {has_cn}')
