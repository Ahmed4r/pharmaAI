import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
text = path.read_text(encoding="utf-8")

old = """try:
    import pytesseract
    from PIL import Image as PILImage
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False"""

new = """try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None  # type: ignore

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False"""

if old in text:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("PATCHED")
else:
    print("PATTERN NOT FOUND")
