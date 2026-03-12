import requests, json, sys

BOT_TOKEN = "8678208722:AAH66Hiu9rqRK8QcTvZDeeIS3UL0FO-G2BY"
CHAT_ID   = "945460800"
HF_API    = "https://ahmedrhegazy-pharma-api.hf.space"

FAKE_CASES = [
    {"query": "warfarin aspirin interaction",         "mode": "cloud"},
    {"query": "metformin and alcohol safety",          "mode": "cloud"},
    {"query": "amoxicillin metronidazole combination", "mode": "cloud"},
]

icons  = {"CRITICAL":"🚨","WARNING":"⚠️","INFO":"ℹ️","SAFE":"✅"}
colors = {"CRITICAL":"🔴","WARNING":"🟡","INFO":"🔵","SAFE":"🟢"}

for i, case in enumerate(FAKE_CASES, 1):
    print(f"\n{'='*55}")
    print(f"[Node 1] Fake webhook payload #{i}: {case['query']}")

    # Node 5 - RAG query to HF
    print(f"[Node 5] Calling HF /query ...")
    r = requests.post(f"{HF_API}/query", json=case, timeout=90)
    r.raise_for_status()
    data = r.json()
    print(f"  severity={data['interaction_severity']}  alert={data['alert_level']}  conf={data['confidence_pct']}%")

    # Node 6 - Format Telegram alert (mirrors n8n JS exactly)
    alert  = data.get("alert_level", "INFO")
    drugs  = " + ".join(d.upper() for d in data.get("drug_name", []))
    src    = data.get("bnf_source_page", [])
    sources = ", ".join(f"BNF80 p.{s['page']}" for s in src[:3]) or "No BNF sources"
    rationale = data.get("clinical_rationale_the_why","")[:500].strip()

    msg = (
        f"{icons.get(alert,'ℹ️')} *PHARMA ALERT* {colors.get(alert,'🔵')}\n"
        f"*Severity:* {data.get('interaction_severity','NONE')}\n"
        f"*Drugs:* {drugs or data['query']}\n\n"
        f"*Clinical Rationale:*\n{rationale}\n\n"
        f"*BNF Sources:* {sources}\n"
        f"*RAG Confidence:* {data['confidence_pct']}%\n\n"
        f"_Query: {data['query']}_\n\n"
        f"📋 _Verify with a licensed pharmacist before clinical decisions_"
    )

    # Node 7 - Route by severity
    print(f"[Node 7] Routing: {alert} -> {'CRITICAL channel' if alert=='CRITICAL' else 'Standard channel'}")

    # Node 8/9 - Send Telegram
    print(f"[Node 8/9] Sending Telegram message ...")
    tg = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
        timeout=15
    )
    res = tg.json()
    if res.get("ok"):
        print(f"  ✅ Sent! Message ID: {res['result']['message_id']}")
    else:
        print(f"  ❌ Error: {res}")

print(f"\n{'='*55}")
print("✅ All 3 fake workflow runs complete. Check Telegram!")