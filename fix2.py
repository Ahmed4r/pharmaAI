import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
text = path.read_text(encoding="utf-8")

old = '''def process_image_bytes(
    image_bytes: bytes,
    filename: str = "image.png",
    **kwargs,
) -> dict:
    """
    Same as process_image_path but accepts raw bytes (e.g. from Streamlit uploader).

    Usage in app.py
    ---------------
        from ocr_engine import process_image_bytes
        result = process_image_bytes(uploaded_file.read(), filename=uploaded_file.name)
    """
    import tempfile

    suffix = Path(filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        return process_image_path(tmp_path, **kwargs)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass'''

new = '''def process_image_bytes(
    image_bytes: bytes,
    filename: str = "image.png",
    **kwargs,
) -> dict:
    """
    Same as process_image_path but accepts raw bytes (e.g. from Streamlit uploader).
    Decodes in memory via cv2.imdecode to avoid temp-file read failures on Windows.
    """
    if not image_bytes:
        return {"status": "error", "error": "Empty image bytes received", "extracted_text": "", "medications": [], "parsed_meds": [], "patient": "", "date": "", "prescriber": "", "dea": "", "confidence": 0.0, "preprocessing": []}

    try:
        deskew = kwargs.pop("deskew", True)
        upscale = kwargs.pop("upscale", True)
        denoise = kwargs.pop("denoise", True)
        adaptive_threshold = kwargs.pop("adaptive_threshold", True)
        morph_close = kwargs.pop("morph_close", True)

        processed, stages = preprocess_image(
            image_bytes,
            deskew=deskew,
            upscale=upscale,
            denoise=denoise,
            adaptive_threshold=adaptive_threshold,
            morph_close=morph_close,
        )
        raw_text, confidence = _run_ocr(processed)
        parsed = parse_prescription_text(raw_text)

        med_labels = [
            f"{m[\'name\']} {m[\'dose\']}{m[\'unit\']}"
            for m in parsed["medications"]
        ]

        return {
            "status":         "success",
            "extracted_text": raw_text,
            "medications":    med_labels,
            "parsed_meds":    parsed["medications"],
            "patient":        parsed.get("patient", ""),
            "date":           parsed.get("date", ""),
            "prescriber":     parsed.get("prescriber", ""),
            "dea":            parsed.get("dea", ""),
            "confidence":     round(confidence, 3),
            "preprocessing":  stages,
        }
    except Exception as exc:
        return {
            "status":         "error",
            "error":          str(exc),
            "extracted_text": "",
            "medications":    [],
            "parsed_meds":    [],
            "patient":        "",
            "date":           "",
            "prescriber":     "",
            "dea":            "",
            "confidence":     0.0,
            "preprocessing":  [],
        }'''

if old in text:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("PATCHED OK")
else:
    print("PATTERN NOT FOUND - len old=" + str(len(old)))
