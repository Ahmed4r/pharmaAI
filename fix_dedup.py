APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    src = f.read()

DUPE = (
    '    # Auto-scroll chat container to bottom so newest message is visible\n'
    '    import streamlit.components.v1 as _cv1\n'
    '    _cv1.html(\n'
    '        """<script>\n'
    '        var els = window.parent.document.querySelectorAll(\n'
    "            '[data-testid=\"stVerticalBlockBorderWrapper\"]');\n"
    '        if (els.length) {\n'
    '            var el = els[els.length - 1];\n'
    '            el.scrollTop = el.scrollHeight;\n'
    '        }\n'
    '        </script>""",\n'
    '        height=0, scrolling=False\n'
    '    )\n'
    '\n'
)
count = src.count(DUPE)
print("occurrences:", count)
if count == 2:
    src = src.replace(DUPE, DUPE, 1)  # keep first
    # remove second
    idx = src.find(DUPE)
    idx2 = src.find(DUPE, idx + len(DUPE))
    src = src[:idx2] + src[idx2 + len(DUPE):]
    with open(APP, 'w', encoding='utf-8') as f:
        f.write(src)
    print("Duplicate removed")
