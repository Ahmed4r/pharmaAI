APP = r'c:\Users\ahmed\pharmaAI\app.py'
with open(APP, encoding='utf-8-sig') as f:
    src = f.read()
src = src.replace(
    '        scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]\n        scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]\n',
    '        scored = [c for c in rag_chunks if c.get("score", 0) >= 0.45]\n'
)
with open(APP, 'w', encoding='utf-8') as f:
    f.write(src)
print('Duplicate removed')
