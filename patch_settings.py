import sys
content = open("app.py", encoding="utf-8").read()
marker = "OCR Engine Configuration\", expanded=False):\n        ocr_engine = st.selectbox"
if marker not in content:
    sys.exit("NOT FOUND - marker missing")
replacement = ("OCR Engine Configuration\", expanded=False):\n"
    "        st.markdown(\"**Groq Vision API (prescription OCR)**\")\n"
    "        st.text_input(\"Groq API Key\", type=\"password\", key=\"groq_api_key\",\n"
    "                      help=\"Get yours at console.groq.com\")\n"
    "        st.divider()\n"
    "        ocr_engine = st.selectbox")
content = content.replace(marker, replacement, 1)
open("app.py", "w", encoding="utf-8").write(content)
print("Settings patch OK")
