content = open('app.py', encoding='utf-8').read()
# Find and replace the f-string with backslash that's illegal in Python 3.10
old = '''                _pill_html = "".join(
                    f"<span class='drug-tag'>{re.sub(r'\\\\s*\\\\(uncertain\\\\)\\\\s*', '', m.get('name',''), flags=re.IGNORECASE).strip()}</span>"
                    for m in parsed_meds if m.get("name")
                )'''
new = '''                _STRIP_PAT = re.compile(r'\\s*\\(uncertain\\)\\s*', re.IGNORECASE)
                _pill_html = "".join(
                    "<span class='drug-tag'>" + _STRIP_PAT.sub('', m.get('name', '')).strip() + "</span>"
                    for m in parsed_meds if m.get("name")
                )'''
if old in content:
    content = content.replace(old, new, 1)
    open('app.py', 'w', encoding='utf-8').write(content)
    print('Fixed OK')
else:
    # Try alternate: just read around line 1369
    lines = content.splitlines()
    for i, ln in enumerate(lines):
        if 're.sub(r' in ln and 'uncertain' in ln and 'pill_html' in lines[max(0,i-2):i+1][-1] if lines[max(0,i-2):i+1] else False:
            print(f'Line {i+1}: {repr(ln)}')
            break
    print('Pattern not found as expected  checking file lines...')
    for i, ln in enumerate(lines[1365:1375], start=1366):
        print(i, repr(ln))
