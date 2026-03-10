APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    lines = f.readlines()

# Find the line with "# Input bar" comment after the chat_box block
for i, ln in enumerate(lines):
    if '#  Input bar' in ln and 'append user msg' in ln:
        # Insert auto-scroll component BEFORE this line
        scroll_code = (
            '    # Auto-scroll chat container to bottom so newest message is visible\n'
            '    import streamlit.components.v1 as _cv1\n'
            '    _cv1.html(\n'
            '        """<script>\n'
            '        var els = window.parent.document.querySelectorAll(\n'
            '            \'[data-testid="stVerticalBlockBorderWrapper"]\');\n'
            '        if (els.length) {\n'
            '            var el = els[els.length - 1];\n'
            '            el.scrollTop = el.scrollHeight;\n'
            '        }\n'
            '        </script>""",\n'
            '        height=0, scrolling=False\n'
            '    )\n'
            '\n'
        )
        lines.insert(i, scroll_code)
        print(f"Inserted auto-scroll at line {i+1}")
        break

with open(APP, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
