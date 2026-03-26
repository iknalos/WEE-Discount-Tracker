import os
import time
import json
import re
import warnings
import smtplib
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from twilio.rest import Client

warnings.filterwarnings("ignore")

# --- 1. SECRETS (Pulled automatically from your GitHub Vault) ---
SENDER_PASSWORD = os.environ.get("GMAIL_PASSWORD")
WEEE_COOKIE_JSON = os.environ.get("WEEE_COOKIE")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_TOKEN")

# --- 2. CONFIGURATION ---
URL = "https://www.sayweee.com/en"

# Email Details
SENDER_EMAIL = "iknalos.luhar@gmail.com"
RECEIVER_EMAILS = [
    "iknalos.luhar@gmail.com",
    "asolanki.work@gmail.com"
]

# Twilio WhatsApp Details
TWILIO_WHATSAPP_SENDER = 'whatsapp:+14155238886' 
WHATSAPP_RECEIVERS = [
    'whatsapp:+16179554893', 
    'whatsapp:+17814064090'  
]

def setup_browser():
    print("Starting up the invisible browser...")
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def send_whatsapp(discounts):
    print("Attempting to send WhatsApp alerts...")
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg_body = f"🛒 *Weee! Deals Alert* 🛒\nWe found {len(discounts)} deals today! Here are the Top 10:\n\n"

        for item in discounts[:10]:
            old_price_str = f"~{item['_raw_old']}~ " if item['_raw_old'] != "??" else ""
            msg_body += f"• *({item['Discount']})* {item['Product']} - {old_price_str}*{item['_raw_new']}*\n"

        msg_body += "\nCheck your email for the full CSV list!"

        for receiver in WHATSAPP_RECEIVERS:
            message = client.messages.create(
                from_=TWILIO_WHATSAPP_SENDER,
                body=msg_body,
                to=receiver
            )
            print(f"WhatsApp sent to {receiver}")
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")

def send_email(html_body, df=None):
    print("Attempting to send email...")
    msg = MIMEMultipart()
    msg['Subject'] = 'Daily Grocery Discount Alert!'
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(RECEIVER_EMAILS)

    msg.attach(MIMEText(html_body, 'html'))

    if df is not None:
        csv_data = df[['Discount', 'Product', 'Original Price', 'Discounted Price']].to_csv(index=False)
        part = MIMEApplication(csv_data.encode('utf-8'))
        part.add_header('Content-Disposition', 'attachment', filename="weee_discounts.csv")
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def load_cookies(driver):
    print("Attempting to load session cookies from GitHub Secrets...")
    try:
        if not WEEE_COOKIE_JSON:
            print("No cookie found in GitHub secrets! Proceeding as guest.")
            return

        cookies = json.loads(WEEE_COOKIE_JSON)

        for cookie in cookies:
            cookie_dict = {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain'),
                'path': cookie.get('path', '/')
            }
            try:
                driver.add_cookie(cookie_dict)
            except Exception:
                pass

        print("Cookies injected successfully!")
    except Exception as e:
        print(f"Error loading cookies: {e}")

def check_discounts():
    driver = setup_browser()

    try:
        print("Navigating to Weee! to establish domain...")
        driver.get("https://www.sayweee.com")
        time.sleep(3)

        load_cookies(driver)

        print(f"Navigating to target URL: {URL}...")
        driver.get(URL)

        print("Waiting for page to load...")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        print("Scanning for discounts...")
        discounted_items = []
        product_names = soup.find_all(attrs={"data-role": "product-name"})

        for p_name in product_names:
            title = p_name.get('title', p_name.text.strip())
            container = p_name.parent
            
            for _ in range(3):
                if container and container.parent and container.parent.name not in ['body', 'html']:
                    container = container.parent

            if container:
                card_text = " ".join(container.get_text(separator=' ').split())
                prices = re.findall(r'\$\d+\.\d{2}(?!\s*/)', card_text)

                if len(prices) >= 2 or "%" in card_text:
                    discount_pct = "??%"
                    new_price = prices[0] if prices else "??"
                    old_price = "??"
                    sort_val = 0

                    if len(prices) >= 2:
                        try:
                            all_p = [float(p.replace('$', '')) for p in prices]
                            new_p = min(all_p)
                            old_p = max(all_p)
                            if old_p > 0:
                                sort_val = int(round((old_p - new_p) / old_p * 100))
                                discount_pct = f"{sort_val}%"
                            new_price = f"${new_p:.2f}"
                            old_price = f"${old_p:.2f}"
                        except Exception:
                            pass
                    elif "%" in card_text:
                        pct_match = re.search(r'(\d+)%', card_text)
                        if pct_match:
                            sort_val = int(pct_match.group(1))
                            discount_pct = f"{sort_val}%"

                    slashed_old = "".join([c + '\u0336' for c in old_price]) if old_price != "??" else "??"

                    deal_dict = {
                        'Discount': discount_pct,
                        'Product': title,
                        'Original Price': slashed_old,
                        'Discounted Price': new_price,
                        '_sort_val': sort_val,
                        '_raw_old': old_price,
                        '_raw_new': new_price
                    }

                    if not any(d['Product'] == title for d in discounted_items):
                        discounted_items.append(deal_dict)

        if discounted_items:
            print(f"Found {len(discounted_items)} potential deals!")
            discounted_items.sort(key=lambda x: x['_sort_val'], reverse=True)
            df = pd.DataFrame(discounted_items)

            html_body = f"""
            <html>
            <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
                .green-text {{ color: #28a745; font-weight: bold; }}
                .strike {{ text-decoration: line-through; color: #888; }}
            </style>
            </head>
            <body>
            <h2>We found {len(discounted_items)} discounts today!</h2>
            <p>Here are the top deals (the full list is attached as a CSV):</p>
            <table>
                <tr>
                    <th>Discount</th>
                    <th>Product</th>
                    <th>Original Price</th>
                    <th>Discounted Price</th>
                </tr>
            """

            for item in discounted_items[:30]:
                raw_old = item['_raw_old']
                old_html = f"<span class='strike'>{raw_old}</span>" if raw_old != "??" else "??"
                html_body += f"<tr><td>{item['Discount']}</td><td>{item['Product']}</td><td>{old_html}</td><td class='green-text'>{item['_raw_new']}</td></tr>"

            html_body += """
            </table>
            </body>
            </html>
            """

            send_email(html_body, df=df)
            send_whatsapp(discounted_items)
        else:
            print("No discounts found. Adjust search terms or check if page structure changed.")

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    check_discounts()