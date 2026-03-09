import pathlib, os, re
path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
src = path.read_text(encoding="utf-8")
nl = chr(10)
dq = chr(34)
old = ("    confidences = [" + nl + "        int(c) for c in data[" + dq + "conf" + dq + "]" + nl + "        if str(c).lstrip(" + dq + "-" + dq + ").isdigit() and int(c) >= 0" + nl + "    ]" + nl + "    mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0" + nl + nl + "    text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)" + nl + "    return text.strip(), round(mean_conf, 3)")
new = ("    conf_vals = [int(c) for c in data[" + dq + "conf" + dq + "] if str(c).lstrip(" + dq + "-" + dq + ").isdigit()]" + nl + "    pos_confs = [c for c in conf_vals if c >= 0]" + nl + "    mean_conf = (sum(pos_confs) / len(pos_confs) / 100.0) if pos_confs else 0.0" + nl + nl + "    high_conf_words = [" + nl + "        data[" + dq + "text" + dq + "][k]" + nl + "        for k in range(len(data[" + dq + "text" + dq + "]))" + nl + "        if str(data[" + dq + "conf" + dq + "][k]).lstrip(" + dq + "-" + dq + ").isdigit()" + nl + "        and int(data[" + dq + "conf" + dq + "][k]) >= 40" + nl + "        and data[" + dq + "text" + dq + "][k].strip()" + nl + "        and all(ord(c) < 128 for c in data[" + dq + "text" + dq + "][k])" + nl + "    ]" + nl + "    clean_text = " + dq + " " + dq + ".join(high_conf_words)" + nl + nl + "    if not clean_text.strip():" + nl + "        clean_text = pytesseract.image_to_string(pil_img, config=_OCR_CONFIG)" + nl + nl + "    return clean_text.strip(), round(mean_conf, 3)")
if old in src:
    src = src.replace(old, new, 1)
    print("run_ocr patched OK")
else:
    print("STILL NOT FOUND")
    idx = src.find("confidences = [")
    print(repr(src[max(0,idx-5):idx+350]))
path.write_text(src, encoding="utf-8")
print("Saved.")