import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\ocr_engine.py")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

# Replace lines 295-302 (0-indexed: 294-301) with the LLM refinement block
# Line 295: "    # After computing mean_conf, before the return:"
# Line 302: "    return clean_text.strip(), round(mean_conf, 3)"
start = None
end = None
for i, line in enumerate(lines):
    if "# After computing mean_conf" in line:
        start = i
    if start and "return clean_text.strip()" in line:
        end = i
        break

print(f"Replacing lines {start+1} to {end+1}")
new_lines = (
    "    # AI refinement: send to BioMistral when confidence is low\n"
    "    if mean_conf < 0.70 and clean_text.strip():\n"
    "        clean_text = _refine_with_llm(clean_text)\n"
    "\n"
    "    return clean_text.strip(), round(mean_conf, 3)\n"
)
lines[start:end+1] = [new_lines]
path.write_text("".join(lines), encoding="utf-8")
print("Done.")