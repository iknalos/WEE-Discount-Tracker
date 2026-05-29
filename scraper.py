import os
import time
import json
import re
import warnings
import smtplib
import datetime
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

# Personal Info Secrets (Portfolio Safe)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECEIVER_EMAILS = [email.strip() for email in os.environ.get("RECEIVER_EMAILS", "").split(",")]
TWILIO_WHATSAPP_SENDER = os.environ.get("TWILIO_SENDER")
WHATSAPP_RECEIVERS = [num.strip() for num in os.environ.get("WHATSAPP_RECEIVERS", "").split(",")]
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip()  # cookie-expiry alerts go here only
COOKIE_WARN_DAYS = 3

# --- 2. CONFIGURATION ---
URL = "https://www.sayweee.com/en"

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

def check_cookie_expiry():
    if not WEEE_COOKIE_JSON:
        return
    try:
        cookies = json.loads(WEEE_COOKIE_JSON)
        expiries = [c.get('expirationDate') for c in cookies if c.get('expirationDate')]
        if not expiries:
            print("DIAG cookie_expiry: no expirationDate fields present, skipping check")
            return
        soonest = min(expiries)
        days_left = (soonest - datetime.datetime.now().timestamp()) / 86400
        print(f"DIAG cookie_expiry: soonest cookie expires in {days_left:.1f} days")
        if days_left < COOKIE_WARN_DAYS:
            send_cookie_warning(days_left)
    except Exception as e:
        print(f"DIAG cookie_expiry: check failed: {e}")

def send_cookie_warning(days_left):
    if not OWNER_EMAIL:
        print("Cookie expiring soon but OWNER_EMAIL not set, no warning sent.")
        return
    msg = MIMEMultipart()
    msg['Subject'] = f"WEEE_COOKIE expires in {days_left:.1f} days - refresh soon"
    msg['From'] = SENDER_EMAIL
    msg['To'] = OWNER_EMAIL
    body = (f"Heads up: your WEEE_COOKIE secret expires in about {days_left:.1f} day(s).\n\n"
            "To avoid breaking the daily scraper:\n"
            "  1. Log into sayweee.com in your browser\n"
            "  2. Export the cookies as JSON\n"
            "  3. Update the WEEE_COOKIE secret in the repo\n")
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [OWNER_EMAIL], msg.as_string())
        print(f"Cookie expiry warning sent to {OWNER_EMAIL}")
    except Exception as e:
        print(f"Failed to send cookie expiry warning: {e}")

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
    check_cookie_expiry()
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
            body_text = " ".join(soup.get_text(separator=' ').split())
            lower = body_text.lower()
            print(f"DIAG title={driver.title!r} url={driver.current_url!r}")
            print(f"DIAG product_name_elements={len(product_names)} "
                  f"has_sign_in={('sign in' in lower) or ('log in' in lower)} "
                  f"has_account={('my account' in lower) or ('my orders' in lower)}")
            print(f"DIAG body_snippet={body_text[:600]!r}")

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    check_discounts()
