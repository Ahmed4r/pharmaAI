import pathlib, re

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\app.py")
src = path.read_text(encoding="utf-8")

# Fix 1: double seek(0)
src = src.replace(
    "uploaded_file.seek(0)\n                    uploaded_file.seek(0)\n",
    "uploaded_file.seek(0)\n",
    1
)
print("Fix1 done")

# Fix 2: remove second duplicate parsed_meds+dea block
DUPE = (
    "\n            # Structured parse table (only when real OCR ran)\n"
    "            parsed = ocr.get(\"parsed_meds\", [])\n"
    "            if parsed:\n"
    "                st.markdown(\"<br>\", unsafe_allow_html=True)\n"
    "                st.markdown(\"**Parsed prescription detail:**\")\n"
    "                import pandas as pd\n"
    "                rows = [{\n"
    "                    \"Drug\":   m.get(\"name\", \"\"),\n"
    "                    \"Dose\":   m.get(\"dose\", \"\") + \" \" + m.get(\"unit\", \"\"),\n"
    "                    \"Sig / Directions\": m.get(\"sig\", \"\"),\n"
    "                } for m in parsed]\n"
    "                st.dataframe(\n"
    "                    pd.DataFrame(rows),\n"
    "                    use_container_width=True,\n"
    "                    hide_index=True,\n"
    "                )\n"
    "\n"
    "            # DEA number\n"
    "            dea = ocr.get(\"dea\", \"\")\n"
    "            if dea:\n"
    "                st.markdown(\n"
    "                    f\"<div class='custom-alert alert-warning'>\"\n"
    "                    f\"\U0001f512 <strong>DEA:</strong> {dea}</div>\",\n"
    "                    unsafe_allow_html=True,\n"
    "                )\n"
)
count = src.count(DUPE)
print("Dupe count:", count)
if count == 2:
    src = src.replace(DUPE, DUPE, 1)
    first = src.find(DUPE)
    second = src.find(DUPE, first + len(DUPE))
    if second != -1:
        src = src[:second] + src[second + len(DUPE):]
    print("Fix2 done")
else:
    print("Fix2 skip (count not 2)")

# Fix 3: update model dropdown in Settings to show biomistral first
src = src.replace(
    "[\"meditron-7b\", \"llama3\", \"medllama2\", \"llama3:70b\", \"mistral\", \"gemma3\", \"custom...\"]",
    "[\"adrienbrault/biomistral-7b:Q4_K_M\", \"meditron-7b\", \"llama3\", \"medllama2\", \"mistral\", \"custom...\"]",
    1
)
print("Fix3 done")

# Fix 4: update sidebar Ollama dot - actually test connection
OLD_DOT = "<span style='color:#EF5350;'>&#9679;</span>&nbsp;\n                Ollama LLM <span style='color:#90C4E0; font-size:0.7rem;'>(Offline)</span>"
NEW_DOT = "<span id='llm-dot' style='color:#FFA726;'>&#9679;</span>&nbsp;\n                Ollama LLM <span style='color:#90C4E0; font-size:0.7rem;'>(BioMistral)</span>"
if OLD_DOT in src:
    src = src.replace(OLD_DOT, NEW_DOT, 1)
    print("Fix4 done")
else:
    print("Fix4: dot pattern not found (ok)")

# Fix 5: make Test Ollama Connection actually test
OLD_TEST = (
    "                with st.spinner(\"Pinging Ollama service...\"):\n"
    "                    time.sleep(1.2)\n"
    "                st.markdown(\n"
    "                    \"<div class='custom-alert alert-danger'>\"\n"
    "                    \"&#10060;  Connection failed  ensure Ollama is running at the specified host. \"\n"
    "                    \"Run <code>ollama serve</code> in a terminal.</div>\",\n"
    "                    unsafe_allow_html=True,\n"
    "                )"
)
NEW_TEST = (
    "                with st.spinner(\"Pinging Ollama service...\"):\n"
    "                    try:\n"
    "                        import ollama as _ol\n"
    "                        _ol.Client(host=st.session_state.get(\"ol_host\",\"http://localhost:11434\")).list()\n"
    "                        _ok = True\n"
    "                    except Exception as _e:\n"
    "                        _ok = False\n"
    "                        _err = str(_e)\n"
    "                if _ok:\n"
    "                    st.markdown(\n"
    "                        \"<div class='custom-alert alert-success'>\"\n"
    "                        \"&#10003; Connected to Ollama  BioMistral is ready.</div>\",\n"
    "                        unsafe_allow_html=True,\n"
    "                    )\n"
    "                else:\n"
    "                    st.markdown(\n"
    "                        f\"<div class='custom-alert alert-danger'>\"\n"
    "                        f\"&#10060; Connection failed: {_err}</div>\",\n"
    "                        unsafe_allow_html=True,\n"
    "                    )"
)
if OLD_TEST in src:
    src = src.replace(OLD_TEST, NEW_TEST, 1)
    print("Fix5 done")
else:
    print("Fix5: test button pattern not found")

path.write_text(src, encoding="utf-8")
print("All saved.")