"""Send today's "free deck" push to each Phone Up! language topic via FCM v1.

Reads phone-up/decks.json (dailyFree rotation, same UTC-day formula as the app)
and .github/phone-up/push_daily_free.json (localized titles/messages).

Env:
  FIREBASE_SERVICE_ACCOUNT  JSON key of a service account with the
                            "Firebase Cloud Messaging API Admin" role.
  DRY_RUN=1                 print the messages instead of sending.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
decks = json.loads((repo / 'phone-up/decks.json').read_text())
config = json.loads((Path(__file__).parent / 'push_daily_free.json').read_text())

rotation = decks.get('dailyFree')
if not rotation or not rotation.get('decks'):
    sys.exit('No dailyFree rotation in decks.json; nothing to send.')
start = dt.date.fromisoformat(rotation['startDate'])
today = dt.datetime.now(dt.timezone.utc).date()
days = (today - start).days
if days < 0:
    sys.exit(f'Rotation starts {start}; nothing to send today ({today}).')
deck_id = rotation['decks'][days % len(rotation['decks'])]
titles = config['titles'].get(deck_id)
if not titles:
    sys.exit(f'No push title for {deck_id}; add it to push_daily_free.json.')

messages = []
for lang, topic in config['topics'].items():
    title_tpl, body = config['messages'][lang]
    messages.append({'message': {
        'topic': topic,
        'notification': {'title': title_tpl.format(title=titles[lang]), 'body': body},
        'apns': {'payload': {'aps': {'sound': 'default'}}},
    }})

print(f'{today}: free deck = {deck_id}')
if os.environ.get('DRY_RUN') == '1':
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    sys.exit(0)

from google.oauth2 import service_account  # noqa: E402
from google.auth.transport.requests import AuthorizedSession  # noqa: E402

info = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT'])
credentials = service_account.Credentials.from_service_account_info(
    info, scopes=['https://www.googleapis.com/auth/firebase.messaging'])
session = AuthorizedSession(credentials)
url = f"https://fcm.googleapis.com/v1/projects/{info['project_id']}/messages:send"
failed = 0
for message in messages:
    response = session.post(url, json=message, timeout=30)
    print(message['message']['topic'], response.status_code)
    if response.status_code != 200:
        failed += 1
        print(response.text[:500])
sys.exit(1 if failed else 0)
