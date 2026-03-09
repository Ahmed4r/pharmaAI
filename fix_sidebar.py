import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\app.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

# Find and fix sidebar Ollama dot
for i, line in enumerate(lines):
    if "Ollama LLM" in line and "Offline" in line:
        lines[i] = "                Ollama LLM <span style='color:#90C4E0; font-size:0.7rem;'>(BioMistral)</span>\n"
        print(f"Fixed sidebar label at line {i+1}")
    if "EF5350" in line and i+1 < len(lines) and "Ollama" in lines[i+1]:
        lines[i] = "                <span style='color:#FFA726;'>&#9679;</span>&nbsp;\n"
        print(f"Fixed sidebar dot color at line {i+1}")

# Find and fix Test Connection button block
for i, line in enumerate(lines):
    if "time.sleep(1.2)" in line and i > 0 and "Pinging" in lines[i-1]:
        # Replace lines i through end of the markdown block
        lines[i] = (
            "                    try:\n"
            "                        import ollama as _ol\n"
            "                        _ol.Client(host=st.session_state.get('ol_host','http://localhost:11434')).list()\n"
            "                        _ok = True\n"
            "                    except Exception as _e:\n"
            "                        _ok = False ; _err = str(_e)\n"
        )
        # Find and replace the error markdown that follows
        j = i + 1
        while j < len(lines) and "unsafe_allow_html" not in lines[j]:
            j += 1
        if j < len(lines):
            # Replace from i+1 to j+1 with the conditional display
            del lines[i+1:j+2]
            lines.insert(i+1,
                "                if _ok:\n"
                "                    st.success('Connected to Ollama  BioMistral is ready.')\n"
                "                else:\n"
                "                    st.error(f'Connection failed: {_err}')\n"
            )
            print(f"Fixed Test Connection at line {i+1}")
        break

path.write_text("".join(lines), encoding="utf-8")
print("Saved.")