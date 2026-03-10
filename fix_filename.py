content = open('app.py', encoding='utf-8').read()

old = '                    result = process_prescription_ocr(uploaded_file.read())\n                    st.session_state.ocr_result = result'
new = '                    st.session_state.ocr_edited = {}\n                    result = process_prescription_ocr(uploaded_file.read(), filename=uploaded_file.name)\n                    st.session_state.ocr_result = result'

if old in content:
    content = content.replace(old, new, 1)
    open('app.py', 'w', encoding='utf-8').write(content)
    print('filename patch OK')
else:
    print('NOT FOUND')
    for i, ln in enumerate(content.splitlines()[1174:1182], 1175):
        print(i, repr(ln))
