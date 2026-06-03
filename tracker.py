import requests
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

PHONE      = "2038147542@vtext.com"
EMAIL_FROM = os.environ["EMAIL_ADDRESS"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
FINNHUB    = "d8ec5fhr01qth3cgkulgd8ec5fhr01qth3cgkum0"
KNOWN_FILE = "known_trades.json"
PRICE_FILE = "price_cache.json"
SIG_FILE   = "signal_cache.json"
MODE       = os.environ.get("RUN_MODE", "signals")
TEST_MODE  = True

WATCHLIST = [
    "NVDA","MSFT","AAPL","AMZN","META","AVGO","GOOGL","AMD","INTC","ORCL",
    "DELL","MU","ADBE","COIN","HOOD","MARA","JPM","GS","BAC","V","SOFI",
    "PLTR","BA","LMT","PG","ABNB","DASH","BE","SPY","QQQ","TSLA","NFLX",
    "CRM","NOW","UBER","PYPL","SHOP","COST","WMT","DIS","XOM","PANW",
    "CRWD","DDOG","ZS","SNOW","QCOM","TXN"
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


def fh(path):
    try:
        r = requests.get(
            f"https://finnhub.io/api/v1{path}&token={FINNHUB}",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        return r.json()
    except:
        return {}


def get_quote(ticker):
    d = fh(f"/quote?symbol={ticker}")
    if not d.get("c"):
        return None
    pc = d["pc"] or 1
    return {
        "price": d["c"],
        "prev": d["pc"],
        "change": round((d["c"] - d["pc"]) / pc * 100, 2),
        "high": d["h"],
        "low": d["l"]
    }


def get_candles(ticker, days=60):
    to = int(datetime.now().timestamp())
    frm = to - 86400 * days
    d = fh(f"/stock/candle?symbol={ticker}&resolution=D&from={frm}&to={to}")
    if d.get("s") == "ok":
        return d.get("c", [])
    return []


def get_metrics(ticker):
    return fh(f"/stock/metric?symbol={ticker}&metric=all").get("metric", {})


def get_recommendation(ticker):
    d = fh(f"/stock/recommendation?symbol={ticker}")
    if isinstance(d, list) and d:
        return d[0]
    return {}


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
    r = closes[-35:]
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
        print(f"Text sent: {msg[:60]}...")
        return True
    except Exception as e:
        print(f"Text failed: {e}")
        return False


def is_must_buy(ticker, quote, closes, rec):
    rsi = calc_rsi(closes)
    macd_bull = calc_macd_bullish(closes)
    sma50 = calc_sma(closes, 50)
    price = quote["price"]
    bull = rec.get("strongBuy", 0) + rec.get("buy", 0)
    total = bull + rec.get("hold", 0) + rec.get("sell", 0) + rec.get("strongSell", 0)
    analyst_bull = (bull / total > 0.6) if total > 0 else False
    score = 50
    if rsi < 42:
        score += 20
    if macd_bull:
        score += 20
    if sma50 and price > sma50:
        score += 15
    if analyst_bull:
        score += 15
    is_buy = rsi < 42 and macd_bull and sma50 and price > sma50 and analyst_bull
    return is_buy, score, rsi


def run_premarket():
    print("Running pre-market debrief...")
    lines = [f"MORNING DEBRIEF — {date.today().strftime('%b %d')}"]
    lines.append("=" * 28)

    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    if spy:
        lines.append(f"SPY  ${spy['price']:.2f}  {spy['change']:+.2f}%")
    if qqq:
        lines.append(f"QQQ  ${qqq['price']:.2f}  {qqq['change']:+.2f}%")

    lines.append("")
    lines.append("TOP MOVERS")
    movers = []
    for ticker in WATCHLIST[:25]:
        q = get_quote(ticker)
        if q:
            movers.append((ticker, q["change"], q["price"]))
    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    for ticker, chg, price in movers[:5]:
        icon = "📈" if chg > 0 else "📉"
        lines.append(f"{icon} {ticker} ${price:.2f} {chg:+.2f}%")

    lines.append("")
    lines.append("TRUMP PORTFOLIO")
    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES))
    trump_moves = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        if q:
            trump_moves.append((ticker, q["change"], q["price"]))
    trump_moves.sort(key=lambda x: x[1], reverse=True)
    for ticker, chg, price in trump_moves[:4]:
        icon = "🟢" if chg > 0 else "🔴"
        lines.append(f"{icon} {ticker} ${price:.2f} {chg:+.2f}%")

    lines.append("")
    lines.append("MUST BUY SETUPS")
    must_buys = []
    for ticker in WATCHLIST[:30]:
        q = get_quote(ticker)
        if not q:
            continue
        closes = get_candles(ticker, 60)
        rec = get_recommendation(ticker)
        mb, score, rsi = is_must_buy(ticker, q, closes, rec)
        if mb:
            must_buys.append((ticker, score, q["price"], rsi))
    if must_buys:
        must_buys.sort(key=lambda x: -x[1])
        for ticker, score, price, rsi in must_buys[:3]:
            lines.append(f"⭐ {ticker} ${price:.2f} Score:{score} RSI:{rsi}")
    else:
        lines.append("No high-conviction setups today")

    send_text("\n".join(lines))


def run_signals():
    print("Running signal scan...")
    price_cache = load_json(PRICE_FILE)
    sig_cache = load_json(SIG_FILE)
    alerts = []
    today = str(date.today())

    for ticker in WATCHLIST:
        q = get_quote(ticker)
        if not q:
            continue
        closes = get_candles(ticker, 60)
        rec = get_recommendation(ticker)

        mb, score, rsi = is_must_buy(ticker, q, closes, rec)
        sig_key = f"mb_{ticker}_{today}"
        if mb and sig_key not in sig_cache:
            alerts.append(
                f"⭐ MUST BUY: {ticker}\n"
                f"Price: ${q['price']:.2f}\n"
                f"Score:{score} RSI:{rsi}\n"
                f"MACD bull + oversold + analyst BUY"
            )
            sig_cache[sig_key] = True

        if abs(q["change"]) >= 5:
            move_key = f"move_{ticker}_{today}"
            if move_key not in sig_cache:
                icon = "🚀" if q["change"] > 0 else "💥"
                alerts.append(
                    f"{icon} BIG MOVE: {ticker}\n"
                    f"{q['change']:+.2f}% today\n"
                    f"Price: ${q['price']:.2f}"
                )
                sig_cache[move_key] = True

        if ticker in price_cache:
            old = price_cache[ticker]["price"]
            chg = (q["price"] - old) / old * 100
            if abs(chg) >= 10:
                chg_key = f"chg10_{ticker}_{today}"
                if chg_key not in sig_cache:
                    direction = "UP" if chg > 0 else "DOWN"
                    alerts.append(
                        f"📊 PRICE ALERT: {ticker}\n"
                        f"{direction} {chg:+.1f}% from baseline\n"
                        f"Was: ${old:.2f} Now: ${q['price']:.2f}"
                    )
                    sig_cache[chg_key] = True

        price_cache[ticker] = {"price": q["price"], "date": today}

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
        alerts.append(f"🇺🇸 NEW TRUMP TRADE\n{len(new_trades)} filed\n{rows}")
        save_json(KNOWN_FILE, known + new_trades)

    save_json(PRICE_FILE, price_cache)
    save_json(SIG_FILE, sig_cache)

    for alert in alerts:
        send_text(alert)
        print(f"Alert sent: {alert[:50]}")

    if not alerts:
        print("No signals triggered.")


def run_daily_close():
    print("Running end of day summary...")
    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES))
    results = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        if q:
            results.append((ticker, q["change"], q["price"]))
    results.sort(key=lambda x: x[1], reverse=True)
    winners = [r for r in results if r[1] > 0]
    losers = [r for r in results if r[1] < 0]

    lines = [f"EOD SUMMARY — {date.today().strftime('%b %d')}"]
    lines.append(f"Winners:{len(winners)} Losers:{len(losers)}")
    lines.append("")
    lines.append("TOP WINNERS")
    for ticker, chg, price in results[:3]:
        lines.append(f"🟢 {ticker} ${price:.2f} {chg:+.2f}%")
    lines.append("")
    lines.append("WATCH TOMORROW")
    for ticker in WATCHLIST[:25]:
        q = get_quote(ticker)
        if not q:
            continue
        closes = get_candles(ticker, 60)
        rsi = calc_rsi(closes)
        if rsi < 35:
            lines.append(f"👀 {ticker} RSI:{rsi} OVERSOLD")
            break

    send_text("\n".join(lines))


def run_weekly():
    print("Running weekly recap...")
    lines = [f"WEEKLY RECAP — {date.today().strftime('%b %d')}"]
    lines.append("=" * 28)
    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES))
    week_results = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        m = get_metrics(ticker)
        w1 = m.get("1WeekPriceReturnDaily")
        if q and w1 is not None:
            week_results.append((ticker, w1, q["price"]))
    week_results.sort(key=lambda x: x[1], reverse=True)
    lines.append("TRUMP PORTFOLIO THIS WEEK")
    for ticker, chg, price in week_results[:5]:
        icon = "🟢" if chg > 0 else "🔴"
        lines.append(f"{icon} {ticker} ${price:.2f} {chg:+.1f}%")

    lines.append("")
    lines.append("NEXT WEEK WATCHLIST")
    setups = []
    for ticker in WATCHLIST[:35]:
        q = get_quote(ticker)
        if not q:
            continue
        closes = get_candles(ticker, 60)
        rsi = calc_rsi(closes)
        macd = calc_macd_bullish(closes)
        sma50 = calc_sma(closes, 50)
        if rsi < 45 and macd and sma50 and q["price"] > sma50:
            setups.append((ticker, rsi, q["price"]))
    for ticker, rsi, price in setups[:5]:
        lines.append(f"⭐ {ticker} ${price:.2f} RSI:{rsi}")

    send_text("\n".join(lines))


def main():
    print(f"Mode: {MODE} — {datetime.now()}")
    if TEST_MODE:
        print("TEST MODE — sending test text")
        send_text(f"TRACKER ONLINE — {date.today()} — system working!")
        return
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
