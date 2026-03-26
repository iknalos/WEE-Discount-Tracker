# 🛒 Weee! Automated Discount Tracker

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![Selenium](https://img.shields.io/badge/Selenium-Headless-43B02A.svg)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF.svg)
![Twilio](https://img.shields.io/badge/Twilio-WhatsApp_API-F22F46.svg)

## 📌 Overview
A fully automated, cloud-hosted web scraping pipeline designed to track daily grocery discounts on [SayWeee](https://www.sayweee.com/). This bot runs autonomously in the cloud every day, scrapes the latest product prices, calculates discount percentages, and delivers real-time alerts via WhatsApp and Email.

This project was built to solve a real-world problem (never missing a good grocery deal) while demonstrating end-to-end automation, data extraction, and API integration.

## 🚀 Features
* **100% Cloud Automated:** Scheduled via GitHub Actions (Cron Jobs) to run daily on a Linux runner. No local machine required.
* **Headless Web Scraping:** Uses Selenium WebDriver and BeautifulSoup4 to render dynamic JavaScript content and extract pricing data.
* **Authenticated Session Management:** Securely injects active session cookies to bypass guest restrictions without hardcoding credentials.
* **Data Processing:** Cleans and parses raw string data into structured formats, sorting deals by highest discount percentage using `pandas`.
* **Multi-Channel Alerting:** * **WhatsApp:** Integrates with the Twilio API to push top-10 deal summaries directly to mobile.
  * **Email:** Uses Python's `smtplib` to send HTML-formatted daily reports with a generated CSV file attached.
* **Secure Credential Vault:** All API keys, passwords, cookies, and personal contact info are abstracted using environment variables and GitHub Secrets.

## 🛠️ Tech Stack
* **Language:** Python 3.10
* **Scraping & Automation:** Selenium, WebDriver Manager, BeautifulSoup4
* **Data Manipulation:** Pandas
* **Integrations:** Twilio API (WhatsApp), SMTP (Gmail)
* **CI/CD & Hosting:** GitHub Actions, Ubuntu Latest

## ⚙️ How It Works
1. **Trigger:** GitHub Actions fires the `schedule.yml` workflow daily at 12:00 PM EST.
2. **Setup:** The cloud runner provisions a Linux environment, installs Google Chrome, and pip-installs dependencies.
3. **Execution:** `scraper.py` is launched. It injects a saved authentication cookie to establish a user session.
4. **Extraction:** The script navigates to the target URLs, scrapes product containers, and uses Regex to extract and calculate price drops.
5. **Delivery:** The structured data is passed to the Twilio client and SMTP server to dispatch notifications.

## 🔒 Environment Variables (Setup)
To run this project locally or in your own repository, you must configure the following environment variables (or GitHub Secrets):

| Variable | Description |
| :--- | :--- |
| `WEEE_COOKIE` | JSON array of active session cookies for SayWeee. |
| `GMAIL_PASSWORD` | 16-character Google App Password for SMTP access. |
| `SENDER_EMAIL` | The email address sending the alerts. |
| `RECEIVER_EMAILS` | Comma-separated list of destination email addresses. |
| `TWILIO_SID` | Your Twilio Account SID. |
| `TWILIO_TOKEN` | Your Twilio Auth Token. |
| `TWILIO_SENDER` | The Twilio Sandbox WhatsApp number. |
| `WHATSAPP_RECEIVERS` | Comma-separated list of verified WhatsApp recipient numbers. |

## ⚠️ Disclaimer
This tool is intended for personal, educational use only. Web scraping should be done responsibly and in accordance with the target website's Terms of Service.
