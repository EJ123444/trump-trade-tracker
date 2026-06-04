import requests
import smtplib
import json
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

PHONE      = "2038147542@vtext.com"
EMAIL_FROM = os.environ["EMAIL_ADDRESS"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
AV_KEY     = "E8W6DEJJDVSWSDEG"
KNOWN_FILE = "known_trades.json"
PRICE_FILE = "price_cache.json"
SIG_FILE   = "signal_cache.json"
MODE       = os.environ.get("RUN_MODE", "signals")

# Core watchlist — kept tight to stay within 25 free API calls/day
WATCHLIST = [
    "SPY","QQQ","NVDA","MSFT","AAPL","AMZN","META","GOOGL","TSLA","AMD",
    "PLTR","COIN","HOOD","INTC","DELL","JPM","GS","BAC","SOFI","BA",
    "LMT","AVGO","ORCL","CRWD","PANW"
]

TRUMP_TRADES = [
    {"ticker":"NVDA","name":"Nvidia","type":"Purchase","date":"2026-01-15","midpoint":3000000},
    {"ticker":"MSFT","name":"Microsoft","type":"Purchase","date":"2026-01-20","midpoint":3000000},
    {"ticker":"AAPL","name":"Apple","type":"Purchase","date":"2026-01-22","midpoint":3000000},
    {"ticker":"AMZN","name":"Amazon","type":"Purchase","date":"2026-01-28","midpoint":3000000},
    {"ticker":"META","name":"Meta","type":"Purchase","date":"2026-01-30","midpoint":375000},
    {"ticker":"AVGO","name":"Broadcom","type":"Purchase","date":"2026-01-18","midpoint":3000000},
    {"ticker":"GOOGL","name":"Alphabet","type":"Purchase","date":"2026-02-03","midpoint":750000},
    {"ticker":"AMD","name":"AMD","type":"Purchase","date":"2026-02-05","midpoint":750000},
    {"ticker":"INTC","name":"Intel","type":"Purchase","date":"2026-02-14","midpoint":750000},
    {"ticker":"DELL","name":"Dell","type":"Purchase","date":"2026-02-10","midpoint":3000000},
    {"ticker":"PLTR","name":"Palantir","type":"Purchase","date":"2026-01-21","midpoint":175000},
    {"ticker":"COIN","name":"Coinbase","type":"Purchase","date":"2026-01-28","midpoint":175000},
    {"ticker":"HOOD","name":"Robinhood","type":"Purchase","date":"2026-02-20","midpoint":175000},
    {"ticker":"SOFI","name":"SoFi","type":"Purchase","date":"2026-02-22","midpoint":75000},
    {"ticker":"JPM","name":"JPMorgan","type":"Purchase","date":"2026-01-25","midpoint":375000},
    {"ticker":"GS","name":"Goldman Sachs","type":"Purchase","date":"2026-01-26","midpoint":375000},
    {"ticker":"BA","name":"Boeing","type":"Purchase","date":"2026-03-05","midpoint":375000},
    {"ticker":"LMT","name":"Lockheed","type":"Purchase","date":"2026-03-08","midpoint":375000},
    {"ticker":"SPY","name":"S&P 500 ETF","type":"Purchase","date":"2026-01-23","midpoint":3000000},
]


def load_json(f):
    try:
        with open(f) as fp:
            return json.load(fp)
    except:
        return {}


def save_json(f, d):
    with open(f, "w") as fp:
        json.dump(d, fp, indent=2)


def av_get(params):
    try:
        params["apikey"] = AV_KEY
        r = requests.get(
            "https://www.alphavantage.co/query",
            params=params,
            timeout=15
        )
        return r.json()
    except Exception as e:
        print(f"AV error: {e}")
        return {}


def get_quote(ticker):
    """Get real-time quote using Alpha Vantage GLOBAL_QUOTE"""
    d = av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    q = d.get("Global Quote", {})
    if not q or not q.get("05. price"):
        print(f"No quote for {ticker}")
        return None
    price = float(q["05. price"])
    prev = float(q["08. previous close"]) if q.get("08. previous close") else price
    change_pct = float(q["10. change percent"].replace("%", "")) if q.get("10. change percent") else 0
    change_abs = float(q["09. change"]) if q.get("09. change") else 0
    volume = int(q["06. volume"]) if q.get("06. volume") else 0
    return {
        "price": price,
        "prev": prev,
        "change": round(change_pct, 2),
        "change_abs": round(change_abs, 2),
        "volume": volume,
        "high": float(q.get("03. high", price)),
        "low": float(q.get("04. low", price)),
    }


def get_daily_closes(ticker, days=60):
    """Get daily close prices for RSI/MACD/SMA calculations"""
    d = av_get({"function": "TIME_SERIES_DAILY", "symbol": ticker, "outputsize": "compact"})
    ts = d.get("Time Series (Daily)", {})
    if not ts:
        print(f"No daily data for {ticker}")
        return []
    closes = [float(v["4. close"]) for v in list(ts.values())[:days]]
    closes.reverse()  # oldest first
    return closes


def calc_rsi(closes, p=14):
    if len(closes) < p + 1:
        return 50
    gains = losses = 0
    for i in range(len(closes) - p, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    ag, al = gains / p, losses / p
    if al == 0:
        return 100
    return round(100 - 100 / (1 + ag / al))


def calc_macd_bullish(closes):
    if len(closes) < 26:
        return False
    def ema(arr, p):
        k = 2 / (p + 1)
        e = arr[0]
        for x in arr[1:]:
            e = x * k + e * (1 - k)
        return e
    r = closes[-35:] if len(closes) >= 35 else closes
    return ema(r, 12) > ema(r, 26)


def calc_sma(closes, p):
    if len(closes) >= p:
        return sum(closes[-p:]) / p
    return None


def send_text(msg):
    try:
        m = MIMEMultipart()
        m["From"] = EMAIL_FROM
        m["To"] = PHONE
        m["Subject"] = ""
        m.attach(MIMEText(msg[:1500], "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(EMAIL_FROM, EMAIL_PASS)
            s.send_message(m)
        print(f"Text sent: {msg[:80]}...")
        return True
    except Exception as e:
        print(f"Text FAILED: {e}")
        return False


def is_must_buy(price, closes, change):
    rsi = calc_rsi(closes)
    macd_bull = calc_macd_bullish(closes)
    sma50 = calc_sma(closes, 50)
    sma20 = calc_sma(closes, 20)
    score = 40
    if rsi < 42:
        score += 20
    if macd_bull:
        score += 20
    if sma50 and price > sma50:
        score += 10
    if sma20 and price > sma20:
        score += 10
    is_buy = rsi < 45 and macd_bull and sma50 and price > sma50
    return is_buy, score, rsi


def run_premarket():
    print("Running pre-market debrief...")
    now = datetime.now().strftime("%I:%M %p")
    lines = [f"MORNING DEBRIEF {date.today().strftime('%b %d')} {now}"]
    lines.append("=" * 30)

    # SPY and QQQ first
    for ticker in ["SPY", "QQQ"]:
        q = get_quote(ticker)
        time.sleep(12)  # AV rate limit: 5 calls/min on free tier
        if q:
            icon = "📈" if q["change"] > 0 else "📉"
            lines.append(f"{icon} {ticker} ${q['price']:.2f} {q['change']:+.2f}%")
        else:
            lines.append(f"{ticker} unavailable")

    lines.append("")
    lines.append("TOP MOVERS")
    movers = []
    # Only fetch 8 quotes to stay within rate limits
    for ticker in ["NVDA", "TSLA", "AAPL", "META", "AMD", "COIN", "PLTR", "MSFT"]:
        q = get_quote(ticker)
        time.sleep(12)
        if q:
            movers.append((ticker, q["change"], q["price"]))

    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    for ticker, chg, price in movers[:5]:
        icon = "📈" if chg > 0 else "📉"
        lines.append(f"{icon} {ticker} ${price:.2f} {chg:+.2f}%")

    lines.append("")
    lines.append("TRUMP PICKS TODAY")
    trump_focus = ["PLTR", "DELL", "COIN", "NVDA", "INTC"]
    for ticker in trump_focus:
        q = get_quote(ticker)
        time.sleep(12)
        if q:
            icon = "🟢" if q["change"] > 0 else "🔴"
            lines.append(f"{icon} {ticker} ${q['price']:.2f} {q['change']:+.2f}%")

    send_text("\n".join(lines))
    print("Pre-market debrief sent!")


def run_signals():
    print("Running signal scan...")
    price_cache = load_json(PRICE_FILE)
    if not isinstance(price_cache, dict):
        price_cache = {}
    sig_cache = load_json(SIG_FILE)
    if not isinstance(sig_cache, dict):
        sig_cache = {}
    alerts = []
    today = str(date.today())
    stocks_checked = 0

    # Focus on most important stocks — stay within API limits
    scan_list = ["SPY", "QQQ", "NVDA", "AAPL", "TSLA", "PLTR", "COIN", "AMD", "META", "MSFT"]

    for ticker in scan_list:
        print(f"Checking {ticker}...")
        q = get_quote(ticker)
        time.sleep(12)  # 5 calls/min rate limit

        if not q:
            continue

        stocks_checked += 1

        # Big move alert (5%+)
        if abs(q["change"]) >= 5:
            move_key = f"move_{ticker}_{today}"
            if move_key not in sig_cache:
                icon = "🚀" if q["change"] > 0 else "💥"
                alerts.append(
                    f"{icon} BIG MOVE: {ticker}\n"
                    f"{q['change']:+.2f}% today\n"
                    f"Price: ${q['price']:.2f}\n"
                    f"Vol: {q['volume']:,}"
                )
                sig_cache[move_key] = True

        # 10% move from baseline
        if ticker in price_cache and isinstance(price_cache[ticker], dict):
            old = price_cache[ticker].get("price", 0)
            if old and old > 0:
                chg = (q["price"] - old) / old * 100
                if abs(chg) >= 10:
                    chg_key = f"chg10_{ticker}_{today}"
                    if chg_key not in sig_cache:
                        direction = "UP" if chg > 0 else "DOWN"
                        alerts.append(
                            f"📊 10% MOVE: {ticker}\n"
                            f"{direction} {chg:+.1f}% from baseline\n"
                            f"Was: ${old:.2f} Now: ${q['price']:.2f}"
                        )
                        sig_cache[chg_key] = True

        price_cache[ticker] = {"price": q["price"], "date": today}

    # Must-buy scan — uses daily candles (more API calls)
    print("Scanning for must-buy setups...")
    for ticker in ["NVDA", "PLTR", "COIN", "AMD", "TSLA"]:
        closes = get_daily_closes(ticker, 60)
        time.sleep(12)
        if not closes:
            continue
        q = get_quote(ticker)
        time.sleep(12)
        if not q:
            continue
        mb, score, rsi = is_must_buy(q["price"], closes, q["change"])
        sig_key = f"mb_{ticker}_{today}"
        if mb and sig_key not in sig_cache:
            alerts.append(
                f"⭐ MUST BUY: {ticker}\n"
                f"Price: ${q['price']:.2f}\n"
                f"Score: {score}/100  RSI: {rsi}\n"
                f"MACD bullish + above SMA50"
            )
            sig_cache[sig_key] = True

    # Check for new Trump trades
    known = load_json(KNOWN_FILE)
    if not isinstance(known, list):
        known = []
    known_keys = {(t["ticker"], t["date"], t["type"]) for t in known}
    new_trades = [t for t in TRUMP_TRADES if (t["ticker"], t["date"], t["type"]) not in known_keys]
    if new_trades:
        rows = "\n".join(
            f"{'BUY' if t['type']=='Purchase' else 'SELL'} {t['ticker']} {t['date']}"
            for t in new_trades
        )
        alerts.append(f"🇺🇸 NEW TRUMP TRADE\n{len(new_trades)} new trades filed\n{rows}")
        save_json(KNOWN_FILE, known + new_trades)

    save_json(PRICE_FILE, price_cache)
    save_json(SIG_FILE, sig_cache)

    if alerts:
        for alert in alerts:
            send_text(alert)
            print(f"Alert sent: {alert[:50]}")
    else:
        msg = f"📊 SCAN {date.today().strftime('%b %d')} {datetime.now().strftime('%I:%M%p')}\n{stocks_checked} stocks checked\nMarkets quiet — no major signals"
        send_text(msg)
        print("Quiet scan — status text sent")


def run_daily_close():
    print("Running end of day summary...")
    lines = [f"EOD SUMMARY — {date.today().strftime('%b %d')}"]
    lines.append("=" * 28)

    results = []
    for ticker in ["SPY", "QQQ", "NVDA", "AAPL", "PLTR", "COIN", "TSLA", "AMD", "META", "MSFT"]:
        q = get_quote(ticker)
        time.sleep(12)
        if q:
            results.append((ticker, q["change"], q["price"]))

    results.sort(key=lambda x: x[1], reverse=True)
    winners = [r for r in results if r[1] > 0]
    losers = [r for r in results if r[1] < 0]

    lines.append(f"Winners: {len(winners)}  Losers: {len(losers)}")
    lines.append("")
    lines.append("TOP WINNERS TODAY")
    for ticker, chg, price in results[:3]:
        lines.append(f"🟢 {ticker} ${price:.2f} {chg:+.2f}%")

    lines.append("")
    lines.append("BIGGEST LOSERS")
    for ticker, chg, price in sorted(results, key=lambda x: x[1])[:2]:
        lines.append(f"🔴 {ticker} ${price:.2f} {chg:+.2f}%")

    lines.append("")
    lines.append("TRUMP PORTFOLIO")
    trump_focus = ["PLTR", "NVDA", "COIN", "DELL", "INTC"]
    for ticker in trump_focus:
        q = get_quote(ticker)
        time.sleep(12)
        if q:
            icon = "🟢" if q["change"] > 0 else "🔴"
            lines.append(f"{icon} {ticker} ${q['price']:.2f} {q['change']:+.2f}%")

    send_text("\n".join(lines))
    print("EOD summary sent!")


def run_weekly():
    print("Running weekly recap...")
    lines = [f"WEEKLY RECAP — {date.today().strftime('%b %d')}"]
    lines.append("=" * 28)

    results = []
    for ticker in ["SPY", "QQQ", "NVDA", "AAPL", "PLTR", "COIN", "TSLA", "AMD"]:
        closes = get_daily_closes(ticker, 10)
        time.sleep(12)
        if closes and len(closes) >= 5:
            week_chg = round((closes[-1] - closes[-5]) / closes[-5] * 100, 2)
            results.append((ticker, week_chg, closes[-1]))

    results.sort(key=lambda x: x[1], reverse=True)
    lines.append("THIS WEEK")
    for ticker, chg, price in results[:5]:
        icon = "🟢" if chg > 0 else "🔴"
        lines.append(f"{icon} {ticker} ${price:.2f} {chg:+.1f}% WoW")

    lines.append("")
    lines.append("NEXT WEEK WATCHLIST")
    setups = []
    for ticker in ["NVDA", "PLTR", "COIN", "AMD", "TSLA", "AAPL", "META"]:
        closes = get_daily_closes(ticker, 60)
        time.sleep(12)
        if not closes:
            continue
        rsi = calc_rsi(closes)
        macd = calc_macd_bullish(closes)
        sma50 = calc_sma(closes, 50)
        if closes and rsi < 45 and macd and sma50 and closes[-1] > sma50:
            setups.append((ticker, rsi, closes[-1]))

    if setups:
        for ticker, rsi, price in setups[:4]:
            lines.append(f"⭐ {ticker} ${price:.2f} RSI:{rsi}")
    else:
        lines.append("No setups yet — check dashboard")

    send_text("\n".join(lines))
    print("Weekly recap sent!")


def main():
    print(f"Mode: {MODE} — {datetime.now()}")
    if MODE == "premarket":
        run_premarket()
    elif MODE == "signals":
        run_signals()
    elif MODE == "daily":
        run_daily_close()
    elif MODE == "weekly":
        run_weekly()
    else:
        run_signals()


if __name__ == "__main__":
    main()
