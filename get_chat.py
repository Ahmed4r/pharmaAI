import requests
BOT_TOKEN = '8678208722:AAH66Hiu9rqRK8QcTvZDeeIS3UL0FO-G2BY'
r = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates', timeout=10)
updates = r.json().get('result', [])
if updates:
    for u in updates[-5:]:
        msg = u.get('message') or u.get('channel_post') or {}
        chat = msg.get('chat', {})
        print(chat.get('id'), chat.get('type'), chat.get('first_name') or chat.get('title'))
else:
    print('NO_UPDATES')