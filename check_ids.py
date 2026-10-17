import re
content = open('web/desktop.html', 'r', encoding='utf-8').read()
ids = re.findall(r"document\.getElementById\(['\"]([^'\"]+)['\"]\)", content)
print('Total getElementById calls:', len(ids))
for i in set(ids):
    if f'id="{i}"' not in content and f"id='{i}'" not in content:
        print('MISSING ID:', i)
