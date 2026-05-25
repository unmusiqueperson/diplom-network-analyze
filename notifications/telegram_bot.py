import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

app = Flask(__name__)

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    })

def format_alert(alert: dict) -> str:
    status    = alert.get('status', 'unknown').upper()
    alertname = alert['labels'].get('alertname', 'unknown')
    severity  = alert['labels'].get('severity', 'unknown')
    summary   = alert['annotations'].get('summary', '')
    description = alert['annotations'].get('description', '')

    emoji = '🔴' if severity == 'critical' else '🟡'

    return (
        f"{emoji} <b>[{status}] {alertname}</b>\n"
        f"Severity: {severity}\n"
        f"Summary: {summary}\n"
        f"Description: {description}"
    )

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    for alert in data.get('alerts', []):
        send_telegram(format_alert(alert))
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
