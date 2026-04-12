import json
import urllib.request
import urllib.parse
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler

class ProxyHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
        
    def do_GET(self):
        if self.path == '/api/rates':
            # Fetch from chogia.vn
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

            try:
                with urllib.request.urlopen(req) as response:
                    html_content = response.read().decode('utf-8')
                    
                    # Parse the html rows
                    rates = []
                    # <tr>...</tr>
                    rows = re.findall(r'<tr.*?>(.*?)</tr>', html_content, re.DOTALL)
                    for row in rows:
                        # Extract data: <td class='price ' id='usd-buy' data-price='26668.0'>26.668,00</td>
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

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    httpd = HTTPServer(('0.0.0.0', port), ProxyHTTPRequestHandler)
    print(f"Serving on port {port}...")
    httpd.serve_forever()
