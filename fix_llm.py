import pathlib

path = pathlib.Path(r"C:\Users\ahmed\pharmaAI\app.py")
src = path.read_text(encoding="utf-8")

OLD_START = "def query_ollama_llm(user_message: str, chat_history: list) -> str:"
OLD_END   = "def check_drug_interactions(drug_list: list) -> list:"

i0 = src.find(OLD_START)
i1 = src.find(OLD_END)

NEW = (
    "def query_ollama_llm(user_message: str, chat_history: list) -> str:\n"
    "    \"\"\"Send prompt + history to local BioMistral via Ollama.\"\"\"\n"
    "    import ollama as _ollama\n"
    "    _MODEL = \"adrienbrault/biomistral-7b:Q4_K_M\"\n"
    "    _HOST  = st.session_state.get(\"ol_host\", \"http://localhost:11434\")\n"
    "    _SYS   = st.session_state.get(\n"
    "        \"ol_system_prompt\",\n"
    "        \"You are an expert clinical pharmacist assistant. Provide concise, \"\n"
    "        \"evidence-based responses. Always recommend consulting a licensed \"\n"
    "        \"pharmacist or physician for patient-specific clinical decisions.\",\n"
    "    )\n"
    "    try:\n"
    "        client = _ollama.Client(host=_HOST)\n"
    "        messages = [{\"role\": \"system\", \"content\": _SYS}]\n"
    "        messages += [{\"role\": m[\"role\"], \"content\": m[\"content\"]} for m in chat_history]\n"
    "        messages.append({\"role\": \"user\", \"content\": user_message})\n"
    "        resp = client.chat(model=_MODEL, messages=messages)\n"
    "        return resp[\"message\"][\"content\"]\n"
    "    except Exception as exc:\n"
    "        return (\n"
    "            f\"**BioMistral offline** - could not reach Ollama at `{_HOST}`\\n\\n\"\n"
    "            f\"Error: `{exc}`\\n\\n\"\n"
    "            \"Make sure Ollama is running (`ollama serve`) and the model is available.\"\n"
    "        )\n"
    "\n"
    "\n"
)

if i0 != -1 and i1 != -1:
    src = src[:i0] + NEW + src[i1:]
    print("query_ollama_llm wired OK")
else:
    print("ERROR: not found", i0, i1)

path.write_text(src, encoding="utf-8")
print("Saved.")