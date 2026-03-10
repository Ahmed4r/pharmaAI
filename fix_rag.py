APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    lines = f.readlines()

# Find and fix line with ) + _rag_block  (the SYS line)
for i, ln in enumerate(lines):
    if ') + _rag_block' in ln and '_SYS' not in ln and '_user_msg' not in ln:
        print(f'SYS rag line {i+1}: {repr(ln.rstrip())}')
        lines[i] = ln.replace(') + _rag_block', ')')
        print(f'  -> fixed')
        break

# Find and fix closing paren of _user_msg clinical block to append _rag_block
# The _user_msg ends with: "and the monitoring parameters."\n        )
for i, ln in enumerate(lines):
    if '"and the monitoring parameters."' in ln:
        # next non-empty line should be the closing paren
        j = i + 1
        while j < len(lines) and lines[j].strip() == '':
            j += 1
        if lines[j].strip() == ')':
            print(f'user_msg close paren line {j+1}: {repr(lines[j].rstrip())}')
            lines[j] = lines[j].replace(')', ') + _rag_block', 1)
            print(f'  -> fixed')
        break

with open(APP, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Patch complete')
