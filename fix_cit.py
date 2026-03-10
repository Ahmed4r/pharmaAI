APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    lines = f.readlines()
for i, ln in enumerate(lines):
    if 'from rag_engine import format_citations' in ln:
        # replace the 3-line block: if rag_chunks..., from rag..., answer +=...
        # lines i-1 = if condition, i = from import, i+1 = answer +=
        lines[i-1] = '        scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]\n'
        lines[i]   = '        if scored:\n'
        lines[i+1] = '            from rag_engine import format_citations\n'
        lines[i+2] = '            answer += f"\\n\\n---\\n{format_citations(scored)}"\n'
        print(f"Patched lines {i} to {i+2}")
        break
with open(APP, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
