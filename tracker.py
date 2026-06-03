import requests
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

# ── Config ────────────────────────────────────────────────────────────────────
PHONE       = "YOURNUMBER@vtext.com"        # ← replace with your number
EMAIL_FROM  = os.environ["EMAIL_ADDRESS"]
EMAIL_PASS  = os.environ["EMAIL_PASSWORD"]
FINNHUB_KEY = "d8ec5fhr01qth3cgkulgd8ec5fhr01qth3cgkum0"
KNOWN_FILE  = "known_trades.json"
PRICE_FILE  = "price_cache.json"
SIGNAL_FILE = "signal_cache.json"
MODE        = os.environ.get("RUN_MODE", "daily")  # premarket | signals | daily | weekly

WATCHLIST = [
    "NVDA","MSFT","AAPL","AMZN","META","AVGO","GOOGL","AMD","INTC","ORCL",
    "DELL","MU","ADBE","COIN","HOOD","MARA","JPM","GS","BAC","V","SOFI",
    "PLTR","BA","LMT","PG","ABNB","DASH","BE","SPY","QQQ","TSLA","NFLX",
    "CRM","NOW","UBER","PYPL","SHOP","COST","WMT","DIS","BRKB","XOM",
    "CVX","AMD","QCOM","TXN","PANW","CRWD","DDOG","ZS","SNOW"
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

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_json(f):
    try:
        with open(f) as fp: return json.load(fp)
    except: return {}

def save_json(f, d):
    with open(f, "w") as fp: json.dump(d, fp, indent=2)

def fh(path):
    try:
        r = requests.get(f"https://finnhub.io/api/v1{path}&token={FINNHUB_KEY}", timeout=10)
        return r.json()
    except: return {}

def get_quote(ticker):
    d = fh(f"/quote?symbol={ticker}")
    if not d.get("c"): return None
    return {"price": d["c"], "prev": d["pc"], "change": round((d["c"]-d["pc"])/d["pc"]*100,2) if d["pc"] else 0, "high": d["h"], "low": d["l"]}

def get_candles(ticker, days=60):
    to = int(datetime.now().timestamp())
    frm = to - 86400 * days
    d = fh(f"/stock/candle?symbol={ticker}&resolution=D&from={frm}&to={to}")
    return d.get("c", []) if d.get("s") == "ok" else []

def calc_rsi(closes, p=14):
    if len(closes) < p+1: return 50
    gains = losses = 0
    for i in range(len(closes)-p, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0: gains += diff
        else: losses += abs(diff)
    ag, al = gains/p, losses/p
    return round(100 - 100/(1 + ag/al)) if al else 100

def calc_macd_bullish(closes):
    if len(closes) < 26: return False
    def ema(arr, p):
        k = 2/(p+1); e = arr[0]
        for x in arr[1:]: e = x*k + e*(1-k)
        return e
    r = closes[-35:]
    return ema(r,12) > ema(r,26)

def calc_sma(closes, p):
    return sum(closes[-p:])/p if len(closes) >= p else None

def send_text(msg):
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

def get_metrics(ticker):
    return fh(f"/stock/metric?symbol={ticker}&metric=all").get("metric", {})

def get_recommendation(ticker):
    d = fh(f"/stock/recommendation?symbol={ticker}")
    return d[0] if isinstance(d, list) and d else {}

def get_target(ticker):
    return fh(f"/stock/price-target?symbol={ticker}")

def score_stock(ticker, quote, closes):
    rsi = calc_rsi(closes)
    macd_bull = calc_macd_bullish(closes)
    sma20 = calc_sma(closes, 20)
    sma50 = calc_sma(closes, 50)
    price = quote["price"]
    score = 50
    if 30 < rsi < 70: score += 10
    if rsi < 40: score += 15
    if rsi > 70: score -= 10
    if macd_bull: score += 15
    if sma20 and price > sma20: score += 10
    if sma50 and price > sma50: score += 10
    if quote["change"] > 0: score += 5
    return max(5, min(98, score)), rsi, macd_bull, sma20, sma50

def is_must_buy(ticker, quote, closes, rec):
    score, rsi, macd_bull, sma20, sma50 = score_stock(ticker, quote, closes)
    price = quote["price"]
    bull_analysts = (rec.get("strongBuy",0) + rec.get("buy",0))
    total_analysts = bull_analysts + rec.get("hold",0) + rec.get("sell",0) + rec.get("strongSell",0)
    analyst_bull = bull_analysts/total_analysts > 0.6 if total_analysts > 0 else False
    return (
        rsi < 42 and
        macd_bull and
        sma50 and price > sma50 and
        analyst_bull and
        score >= 70
    ), score, rsi

# ── Modes ─────────────────────────────────────────────────────────────────────

def run_premarket():
    """9:30 AM — full morning debrief"""
    print("Running pre-market debrief...")
    lines = [f"MORNING DEBRIEF — {date.today().strftime('%b %d')}"]
    lines.append("=" * 30)

    # Market overview
    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    if spy: lines.append(f"SPY  {spy['price']:.2f}  {spy['change']:+.2f}%")
    if qqq: lines.append(f"QQQ  {qqq['price']:.2f}  {qqq['change']:+.2f}%")

    lines.append("")
    lines.append("TOP MOVERS TODAY")

    # Scan watchlist for top movers
    movers = []
    for ticker in WATCHLIST[:30]:
        q = get_quote(ticker)
        if q: movers.append((ticker, q["change"], q["price"]))

    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    for ticker, chg, price in movers[:5]:
        icon = "📈" if chg > 0 else "📉"
        lines.append(f"{icon} {ticker}  ${price:.2f}  {chg:+.2f}%")

    lines.append("")
    lines.append("TRUMP PORTFOLIO")
    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES if t["type"]=="Purchase"))
    trump_moves = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        if q: trump_moves.append((ticker, q["change"], q["price"]))
    trump_moves.sort(key=lambda x: x[1], reverse=True)
    for ticker, chg, price in trump_moves[:5]:
        icon = "🟢" if chg > 0 else "🔴"
        lines.append(f"{icon} {ticker}  ${price:.2f}  {chg:+.2f}%")

    lines.append("")
    lines.append("MUST BUY SETUPS")
    must_buys = []
    for ticker in WATCHLIST[:40]:
        q = get_quote(ticker)
        if not q: continue
        closes = get_candles(ticker, 60)
        rec = get_recommendation(ticker)
        mb, score, rsi = is_must_buy(ticker, q, closes, rec)
        if mb: must_buys.append((ticker, score, q["price"], rsi))

    if must_buys:
        must_buys.sort(key=lambda x: -x[1])
        for ticker, score, price, rsi in must_buys[:3]:
            lines.append(f"⭐ {ticker}  ${price:.2f}  Score:{score}  RSI:{rsi}")
    else:
        lines.append("No high-conviction setups today")

    send_text("\n".join(lines))

def run_signals():
    """Intraday — scan for must-buy signals and major price moves"""
    print("Running signal scan...")
    price_cache = load_json(PRICE_FILE)
    signal_cache = load_json(SIGNAL_FILE)
    alerts = []

    for ticker in WATCHLIST:
        q = get_quote(ticker)
        if not q: continue
        closes = get_candles(ticker, 60)
        rec = get_recommendation(ticker)

        # Must buy signal
        mb, score, rsi = is_must_buy(ticker, q, closes, rec)
        sig_key = f"mustbuy_{ticker}_{date.today()}"
        if mb and sig_key not in signal_cache:
            alerts.append(f"⭐ MUST BUY: {ticker}\nPrice: ${q['price']:.2f}\nScore: {score}/100  RSI: {rsi}\nMACD bullish + oversold + analyst consensus BUY")
            signal_cache[sig_key] = True

        # Big price move
        if abs(q["change"]) >= 0.1:
            move_key = f"move_{ticker}_{date.today()}"
            if move_key not in signal_cache:
                icon = "🚀" if q["change"] > 0 else "💥"
                alerts.append(f"{icon} BIG MOVE: {ticker}\n{q['change']:+.2f}% today\nPrice: ${q['price']:.2f}")
                signal_cache[move_key] = True

        # Price vs cache (10% move)
        if ticker in price_cache:
            old = price_cache[ticker]["price"]
            chg = (q["price"] - old) / old * 100
            if abs(chg) >= 10:
                chg_key = f"chg10_{ticker}_{date.today()}"
                if chg_key not in signal_cache:
                    dir = "UP" if chg > 0 else "DOWN"
                    alerts.append(f"📊 PRICE ALERT: {ticker}\n{dir} {chg:+.1f}% from baseline\nWas: ${old:.2f}  Now: ${q['price']:.2f}")
                    signal_cache[chg_key] = True

        # 52 week high breakout
        m = get_metrics(ticker)
        w52h = m.get("52WeekHigh")
        if w52h and q["price"] >= w52h * 0.99:
            brk_key = f"52wk_{ticker}_{date.today()}"
            if brk_key not in signal_cache:
                alerts.append(f"🔥 52W HIGH BREAKOUT: {ticker}\nPrice: ${q['price']:.2f}\n52W High: ${w52h:.2f}\nMomentum stocks keep running!")
                signal_cache[brk_key] = True

        price_cache[ticker] = {"price": q["price"], "date": str(date.today())}

    save_json(PRICE_FILE, price_cache)
    save_json(SIGNAL_FILE, signal_cache)

    # Check for new Trump trades
    known = load_json(KNOWN_FILE) if isinstance(load_json(KNOWN_FILE), list) else []
    known_keys = {(t["ticker"], t["date"], t["type"]) for t in known}
    new_trades = [t for t in TRUMP_TRADES if (t["ticker"], t["date"], t["type"]) not in known_keys]
    if new_trades:
        rows = "\n".join(f"{'BUY' if t['type']=='Purchase' else 'SELL'} {t['ticker']} {t['date']}" for t in new_trades)
        alerts.append(f"🇺🇸 NEW TRUMP TRADE\n{len(new_trades)} filed\n{rows}")
        save_json(KNOWN_FILE, known + new_trades)

    for alert in alerts:
        send_text(alert)
        print(f"Alert sent: {alert[:50]}")

   if not alerts:
    print("No signals triggered.")
    send_text(f"TRACKER ALIVE {date.today()} — no signals today")

def run_daily_close():
    """4 PM — end of day portfolio summary"""
    print("Running end of day summary...")
    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES if t["type"]=="Purchase"))
    results = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        if q: results.append((ticker, q["change"], q["price"]))

    results.sort(key=lambda x: x[1], reverse=True)
    winners = [r for r in results if r[1] > 0]
    losers  = [r for r in results if r[1] < 0]

    lines = [f"EOD SUMMARY — {date.today().strftime('%b %d')}"]
    lines.append(f"Winners: {len(winners)}  Losers: {len(losers)}")
    lines.append("")
    lines.append("TOP WINNERS")
    for ticker, chg, price in results[:3]:
        lines.append(f"🟢 {ticker}  ${price:.2f}  {chg:+.2f}%")
    lines.append("")
    lines.append("BIGGEST LOSERS")
    for ticker, chg, price in sorted(results, key=lambda x: x[1])[:3]:
        lines.append(f"🔴 {ticker}  ${price:.2f}  {chg:+.2f}%")

    # Best must-buy for tomorrow
    lines.append("")
    lines.append("WATCH TOMORROW")
    for ticker in WATCHLIST[:25]:
        q = get_quote(ticker)
        if not q: continue
        closes = get_candles(ticker, 60)
        rsi = calc_rsi(closes)
        if rsi < 35:
            lines.append(f"👀 {ticker}  RSI:{rsi}  OVERSOLD")
            break

    send_text("\n".join(lines))

def run_weekly():
    """Friday — weekly recap + next week watchlist"""
    print("Running weekly recap...")
    lines = [f"WEEKLY RECAP — Week of {date.today().strftime('%b %d')}"]
    lines.append("=" * 30)

    trump_tickers = list(set(t["ticker"] for t in TRUMP_TRADES if t["type"]=="Purchase"))
    week_results = []
    for ticker in trump_tickers:
        q = get_quote(ticker)
        m = get_metrics(ticker)
        w1chg = m.get("1WeekPriceReturnDaily")
        if q and w1chg is not None:
            week_results.append((ticker, w1chg, q["price"]))

    week_results.sort(key=lambda x: x[1], reverse=True)
    lines.append("TRUMP PORTFOLIO THIS WEEK")
    for ticker, chg, price in week_results[:5]:
        icon = "🟢" if chg > 0 else "🔴"
        lines.append(f"{icon} {ticker}  ${price:.2f}  {chg:+.1f}% WoW")

    lines.append("")
    lines.append("NEXT WEEK WATCHLIST")
    setups = []
    for ticker in WATCHLIST[:40]:
        q = get_quote(ticker)
        if not q: continue
        closes = get_candles(ticker, 60)
        rsi = calc_rsi(closes)
        macd = calc_macd_bullish(closes)
        sma50 = calc_sma(closes, 50)
        if rsi < 45 and macd and sma50 and q["price"] > sma50:
            setups.append((ticker, rsi, q["price"]))

    for ticker, rsi, price in setups[:5]:
        lines.append(f"⭐ {ticker}  ${price:.2f}  RSI:{rsi}")

    send_text("\n".join(lines))

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Running mode: {MODE} — {datetime.now()}")
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
