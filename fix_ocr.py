import pathlib, os, re

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
text = path.read_text(encoding="utf-8")

# --- 1. Replace OCR config to use ara+eng, no whitelist (whitelist breaks multi-lang) ---
old_cfg = """_OCR_CONFIG = (
    "--oem 3 "          # LSTM engine
    "--psm 6 "          # Assume uniform block of text
    "-c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789 .,/:()-+%"
)"""

new_cfg = """# Two configs: bilingual (ara+eng) when Arabic tessdata is present, else English-only
_ARA_TESSDATA = os.path.isfile(r"C:\\Program Files\\Tesseract-OCR\\tessdata\\ara.traineddata")
_LANG = "ara+eng" if _ARA_TESSDATA else "eng"
_OCR_CONFIG = f"--oem 3 --psm 6 -l {_LANG}" """

if old_cfg in text:
    text = text.replace(old_cfg, new_cfg, 1)
    print("Config patched")
else:
    print("ERROR: Config pattern not found")

# --- 2. Replace _run_ocr to filter low-confidence words ---
old_run = """    pil_img = PILImage.fromarray(processed_gray)

    # Get per-word confidence data
    data = pytesseract.image_to_data(
        pil_img,
        config=_OCR_CONFIG,
        output_type=pytesseract.Output.DICT,
    )

    confidences = [
        int(c) for c in data["conf"]
        if str(c).lstrip("-").isdigit() and int(c) >= 0
    ]
    mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)
    return text.strip(), round(mean_conf, 3)"""

new_run = """    pil_img = PILImage.fromarray(processed_gray)

    # Get per-word confidence data
    data = pytesseract.image_to_data(
        pil_img,
        config=_OCR_CONFIG,
        output_type=pytesseract.Output.DICT,
    )

    conf_vals = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit()]
    pos_confs = [c for c in conf_vals if c >= 0]
    mean_conf = (sum(pos_confs) / len(pos_confs) / 100.0) if pos_confs else 0.0

    # Rebuild text keeping only words with confidence >= 40 (reduces Arabic noise)
    high_conf_words = [
        data["text"][i]
        for i in range(len(data["text"]))
        if str(data["conf"][i]).lstrip("-").isdigit()
        and int(data["conf"][i]) >= 40
        and data["text"][i].strip()
        # Keep only ASCII-printable words (drop Arabic tokens)
        and all(ord(c) < 128 for c in data["text"][i])
    ]
    clean_text = " ".join(high_conf_words)

    # Fall back to full raw text if filtering removed everything
    if not clean_text.strip():
        clean_text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)

    return clean_text.strip(), round(mean_conf, 3)"""

if old_run in text:
    text = text.replace(old_run, new_run, 1)
    print("_run_ocr patched")
else:
    # try normalising line endings
    old_run2 = old_run.replace("\n", "\r\n")
    if old_run2 in text:
        text = text.replace(old_run2, new_run, 1)
        print("_run_ocr patched (CRLF)")
    else:
        print("ERROR: _run_ocr pattern not found")
        # show actual snippet for debug
        idx = text.find("pil_img = PILImage.fromarray")
        print(repr(text[idx:idx+600]))

path.write_text(text, encoding="utf-8")
print("Done")
