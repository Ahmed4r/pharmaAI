content = open('app.py', encoding='utf-8').read()

# 1. Add dotenv load after the existing imports block (after 'from datetime import datetime')
OLD_TOP = 'import re\nimport streamlit as st\nimport time\nfrom datetime import datetime'
NEW_TOP = ('import re\nimport streamlit as st\nimport time\nfrom datetime import datetime\nimport os as _os\n\n'
           '# Load .env file (local dev)  must run before any os.environ reads\n'
           'try:\n'
           '    from dotenv import load_dotenv as _load_dotenv\n'
           '    _load_dotenv(override=False)  # does NOT overwrite already-set env vars\n'
           'except ImportError:\n'
           '    pass  # python-dotenv optional; env vars may be set another way\n')

if OLD_TOP not in content:
    print('TOP anchor not found'); exit(1)
content = content.replace(OLD_TOP, NEW_TOP, 1)
print('[1/2] dotenv load block added OK')

# 2. Update the api_key lookup in process_prescription_ocr to also check st.secrets
OLD_KEY = ('        api_key = (\n'
           '            st.session_state.get("groq_api_key", "").strip()\n'
           '            or _os.environ.get("GROQ_API_KEY", "")\n'
           '        )')
NEW_KEY = ('        api_key = (\n'
           '            st.session_state.get("groq_api_key", "").strip()\n'
           '            or _os.environ.get("GROQ_API_KEY", "")\n'
           '            or st.secrets.get("GROQ_API_KEY", "")\n'
           '        )')

if OLD_KEY not in content:
    print('KEY anchor not found'); exit(1)
content = content.replace(OLD_KEY, NEW_KEY, 1)
print('[2/2] st.secrets fallback added OK')

open('app.py', 'w', encoding='utf-8').write(content)
print('Done.')
