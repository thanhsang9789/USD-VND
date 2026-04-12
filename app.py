import os
import json
import urllib.request
import urllib.parse
import re
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Load .env file securely for local testing without leaking to GitHub
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k.strip()] = v.strip()

# Telegram Bot Config (Load from Environment Variables)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
TARGET_BID_THRESHOLD = 26668.0

def fetch_chogia_data():
    url = "https://chogia.vn/get-live-price.php"
    params = {
        "k": "8fgY0d9s#8g023j5lagu9$8G72935jsaf987DF2935^uflskaB@j9873Y5",
        "t": "currencynames"
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    req = urllib.request.Request(
        full_url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    )

    with urllib.request.urlopen(req) as response:
        html_content = response.read().decode('utf-8')
        
        rates = []
        rows = re.findall(r'<tr.*?>(.*?)</tr>', html_content, re.DOTALL)
        for row in rows:
            currency_match = re.search(r'<strong>(.*?)</strong>', row)
            name_match = re.findall(r'<td>(.*?)</td>', row)
            price_matches = re.findall(r"data-price='([^']*)'>([^<]*)<", row)

            if currency_match and name_match and len(price_matches) >= 2:
                currency_code = currency_match.group(1).strip()
                name = name_match[0] if name_match else ""
                name = re.sub(r'<[^>]+>', '', name).strip()
                
                buy_price_val = price_matches[0][0]
                buy_price_fmt = price_matches[0][1]
                sell_price_val = price_matches[1][0]
                sell_price_fmt = price_matches[1][1]

                rates.append({
                    "code": currency_code,
                    "name": name,
                    "buy_raw": buy_price_val,
                    "buy_formatted": buy_price_fmt,
                    "sell_raw": sell_price_val,
                    "sell_formatted": sell_price_fmt
                })
        return rates

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': TELEGRAM_CHAT_ID, 'text': message}).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    try:
        urllib.request.urlopen(req)
        print(f"[Telegram] Alert sent: {message}")
    except Exception as e:
        print(f"[Telegram] Failed to send alert: {e}")

def monitor_usd_alert():
    print("[Telegram Watcher] Bot started watching for USD >= 27,000 VND...")
    alert_triggered = False

    while True:
        try:
            rates = fetch_chogia_data()
            for rate in rates:
                if rate['code'] == 'USD':
                    # Sometimes buy_raw might have non-numeric or be empty, safeguard it
                    try:
                        buy_price = float(rate['buy_raw'])
                    except ValueError:
                        continue

                    print(f"Watchdog: Current USD Bid is {rate['buy_formatted']} ₫ ({buy_price})")
                    
                    if buy_price >= TARGET_BID_THRESHOLD and not alert_triggered:
                        msg = f"🚨 CẢNH BÁO THỊ TRƯỜNG!\nGiá USD (Mua vào) chợ đen vừa chạm mốc {rate['buy_formatted']} ₫"
                        send_telegram_alert(msg)
                        alert_triggered = True  # Prevent spamming alerts every 2 minutes
                    elif buy_price < TARGET_BID_THRESHOLD:
                        # Reset the trigger if price drops below the threshold again
                        alert_triggered = False
                    
                    break # Checked USD, exit loop
            
        except Exception as e:
            print(f"[Telegram Watcher] Error fetching data: {e}")
        
        # Check every 2 minutes (120 seconds) to avoid ban
        time.sleep(120)

class ProxyHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
        
    def do_GET(self):
        if self.path == '/api/rates':
            try:
                rates = fetch_chogia_data()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                super().end_headers()
                self.wfile.write(json.dumps(rates).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                super().end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            if self.path == '/':
                self.path = '/index.html'
            super().do_GET()


if __name__ == '__main__':
    # Start Telegram background monitor thread
    watcher_thread = threading.Thread(target=monitor_usd_alert, daemon=True)
    watcher_thread.start()

    port = int(os.environ.get('PORT', 8080))
    httpd = HTTPServer(('0.0.0.0', port), ProxyHTTPRequestHandler)
    print(f"Serving on port {port}...")
    httpd.serve_forever()
