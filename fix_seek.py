import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\app.py")
text = path.read_text(encoding="utf-8")

old = "result = process_prescription_ocr(uploaded_file.read())"
new = "uploaded_file.seek(0)\n                    result = process_prescription_ocr(uploaded_file.read())"

if old in text:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("PATCHED")
else:
    print("PATTERN NOT FOUND")
