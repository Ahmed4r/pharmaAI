APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    lines = f.readlines()
for i, ln in enumerate(lines):
    if ') + _rag_block' in ln:
        print(f'line {i+1}: {repr(ln.rstrip())}')
        lines[i] = ln.replace(') + _rag_block', ')')
        print(f'  fixed')
with open(APP, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
