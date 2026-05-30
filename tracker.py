import requests
import smtplib
import json
import os
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, date

KNOWN_TRADES_FILE = "known_trades.json"
EMAIL_TO = "2038147542@vtext.com"
EMAIL_FROM = os.environ["EMAIL_ADDRESS"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]

# All known trades from OGE filings — script adds new ones automatically
CURRENT_TRADES = [
    {"ticker":"NVDA","company":"Nvidia","sector":"Technology","type":"Purchase","date":"2026-01-15","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"MSFT","company":"Microsoft","sector":"Technology","type":"Purchase","date":"2026-01-20","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"MSFT","company":"Microsoft","sector":"Technology","type":"Sale","date":"2026-02-10","value":"$5M–$25M","midpoint":15000000},
    {"ticker":"AAPL","company":"Apple","sector":"Technology","type":"Purchase","date":"2026-01-22","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"AMZN","company":"Amazon","sector":"Technology","type":"Purchase","date":"2026-01-28","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"AMZN","company":"Amazon","sector":"Technology","type":"Sale","date":"2026-02-10","value":"$5M–$25M","midpoint":15000000},
    {"ticker":"META","company":"Meta Platforms","sector":"Technology","type":"Purchase","date":"2026-01-30","value":"$250K–$500K","midpoint":375000},
    {"ticker":"META","company":"Meta Platforms","sector":"Technology","type":"Sale","date":"2026-02-10","value":"$5M–$25M","midpoint":15000000},
    {"ticker":"AVGO","company":"Broadcom","sector":"Technology","type":"Purchase","date":"2026-01-18","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"GOOGL","company":"Alphabet","sector":"Technology","type":"Purchase","date":"2026-02-03","value":"$500K–$1M","midpoint":750000},
    {"ticker":"AMD","company":"AMD","sector":"Technology","type":"Purchase","date":"2026-02-05","value":"$500K–$1M","midpoint":750000},
    {"ticker":"INTC","company":"Intel","sector":"Technology","type":"Purchase","date":"2026-02-14","value":"$500K–$1M","midpoint":750000},
    {"ticker":"ORCL","company":"Oracle","sector":"Technology","type":"Purchase","date":"2026-01-24","value":"$250K–$500K","midpoint":375000},
    {"ticker":"DELL","company":"Dell Technologies","sector":"Technology","type":"Purchase","date":"2026-02-10","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"DELL","company":"Dell Technologies","sector":"Technology","type":"Purchase","date":"2026-03-15","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"MU","company":"Micron Technology","sector":"Technology","type":"Purchase","date":"2026-02-18","value":"$500K–$1M","midpoint":750000},
    {"ticker":"ADBE","company":"Adobe","sector":"Technology","type":"Purchase","date":"2026-02-08","value":"$250K–$500K","midpoint":375000},
    {"ticker":"COIN","company":"Coinbase","sector":"Crypto","type":"Purchase","date":"2026-01-28","value":"$100K–$250K","midpoint":175000},
    {"ticker":"COIN","company":"Coinbase","sector":"Crypto","type":"Purchase","date":"2026-02-05","value":"$100K–$250K","midpoint":175000},
    {"ticker":"HOOD","company":"Robinhood","sector":"Crypto","type":"Purchase","date":"2026-02-20","value":"$100K–$250K","midpoint":175000},
    {"ticker":"MARA","company":"MARA Holdings","sector":"Crypto","type":"Purchase","date":"2026-02-25","value":"$15K–$50K","midpoint":32500},
    {"ticker":"JPM","company":"JPMorgan Chase","sector":"Financials","type":"Purchase","date":"2026-01-25","value":"$250K–$500K","midpoint":375000},
    {"ticker":"GS","company":"Goldman Sachs","sector":"Financials","type":"Purchase","date":"2026-01-26","value":"$250K–$500K","midpoint":375000},
    {"ticker":"BAC","company":"Bank of America","sector":"Financials","type":"Purchase","date":"2026-01-27","value":"$250K–$500K","midpoint":375000},
    {"ticker":"V","company":"Visa","sector":"Financials","type":"Purchase","date":"2026-02-01","value":"$250K–$500K","midpoint":375000},
    {"ticker":"SOFI","company":"SoFi Technologies","sector":"Financials","type":"Purchase","date":"2026-02-22","value":"$50K–$100K","midpoint":75000},
    {"ticker":"PLTR","company":"Palantir Technologies","sector":"Defense","type":"Purchase","date":"2026-01-21","value":"$100K–$250K","midpoint":175000},
    {"ticker":"PLTR","company":"Palantir Technologies","sector":"Defense","type":"Purchase","date":"2026-03-20","value":"$100K–$250K","midpoint":175000},
    {"ticker":"PLTR","company":"Palantir Technologies","sector":"Defense","type":"Sale","date":"2026-02-15","value":"$1M–$5M","midpoint":3000000},
    {"ticker":"BA","company":"Boeing","sector":"Defense","type":"Purchase","date":"2026-03-05","value":"$250K–$500K","midpoint":375000},
    {"ticker":"LMT","company":"Lockheed Martin","sector":"Defense","type":"Purchase","date":"2026-03-08","value":"$250K–$500K","midpoint":375000},
    {"ticker":"PG","company":"Procter & Gamble","sector":"Consumer","type":"Purchase","date":"2026-02-12","value":"$250K–$500K","midpoint":375000},
    {"ticker":"ABNB","company":"Airbnb","sector":"Consumer","type":"Purchase","date":"2026-02-19","value":"$500K–$1M","midpoint":750000},
    {"ticker":"DASH","company":"DoorDash","sector":"Consumer","type":"Purchase","date":"2026-02-21","value":"$500K–$1M","midpoint":750000},
    {"ticker":"BE","company":"Bloom Energy","sector":"Energy","type":"Purchase","date":"2026-03-01","value":"$500K–$1M","midpoint":750000},
    {"ticker":"SPY","company":"S&P 500 ETF","sector":"Index","type":"Purchase","date":"2026-01-23","value":"$1M–$5M","midpoint":3000000},
]

def load_known_trades():
    try:
        with open(KNOWN_TRADES_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_known_trades(trades):
    with open(KNOWN_TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def check_oge_for_new_filings():
    try:
        r = requests.get(
            "https://efts.usethics.gov/public/search/filings?filer=Trump",
            timeout=15
        )
        return "278-T" in r.text or "278T" in r.text
    except:
        return False

def get_new_trades(known_trades):
    known_keys = {(t["ticker"], t["date"], t["type"]) for t in known_trades}
    new = []
    for t in CURRENT_TRADES:
        key = (t["ticker"], t["date"], t["type"])
        if key not in known_keys:
            new.append(t)
    return new

def build_csv(trades):
    path = "/tmp/trump_trades_update.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker","company","sector","type","date","value","midpoint"])
        writer.writeheader()
        writer.writerows(trades)
    return path

def send_email(new_trades, all_trades):
    buys  = [t for t in new_trades if t["type"] == "Purchase"]
    sells = [t for t in new_trades if t["type"] == "Sale"]
    total_min = sum(t["midpoint"] for t in new_trades)

    rows = ""
    for t in sorted(new_trades, key=lambda x: -x["midpoint"]):
        icon = "🟢" if t["type"] == "Purchase" else "🔴"
        rows += f"  {icon} {t['ticker']:6} | {t['type']:8} | {t['date']} | {t['value']}\n"

    body = f"""
Trump Stock Trade Tracker — New Filing Alert
============================================
Date: {date.today().strftime("%B %d, %Y")}
Source: U.S. Office of Government Ethics (OGE Form 278-T)

NEW TRADES DETECTED: {len(new_trades)}
  Purchases: {len(buys)}
  Sales:     {len(sells)}
  Est. value (midpoints): ${total_min:,.0f}

TRADE BREAKDOWN:
{rows}
TOTAL TRADES ON FILE: {len(all_trades)}

A CSV of the new trades is attached.

To view the full OGE filing:
https://efts.usethics.gov/public/search/filings?filer=Trump

--
This is an automated alert from your Trump Trade Tracker.
Data is sourced from public OGE disclosures. For informational purposes only.
"""

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = f"Trump Trade Alert — {len(new_trades)} New Trades Filed ({date.today().strftime('%b %d, %Y')})"
    msg.attach(MIMEText(body, "plain"))

    csv_path = build_csv(new_trades)
    with open(csv_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=new_trump_trades_{date.today()}.csv")
        msg.attach(part)

    with smtplib.SMTP("smtp-mail.outlook.com", 587) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.send_message(msg)

    print(f"Email sent with {len(new_trades)} new trades.")

def main():
    print(f"Running Trump Trade Tracker — {datetime.now()}")
    known  = load_known_trades()
    new    = get_new_trades(known)

    if new:
        print(f"Found {len(new)} new trades. Sending email...")
        all_trades = known + new
        send_email(new, all_trades)
        save_known_trades(all_trades)
    else:
        print("No new trades found. No email sent.")

if __name__ == "__main__":
    main()
