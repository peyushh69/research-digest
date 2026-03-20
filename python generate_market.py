# ================================================================
#  QUANTIS — MARKET DASHBOARD GENERATOR
#
#  Abhi: Placeholder page banata hai
#  Baad mein: FII data, Bond market, Market breadth etc. add honge
#
#  Chalayein: python generate_market.py
# ================================================================

import os
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
os.environ.pop("GOOGLE_API_KEY", None)

WEBSITE_TITLE = "Quantis"

# ================================================================
#  TICKER
# ================================================================

def fetch_ticker():
    symbols = {
        "NIFTY 50":   "^NSEI",
        "SENSEX":     "^BSESN",
        "BANK NIFTY": "^NSEBANK",
        "S&P 500":    "^GSPC",
        "NASDAQ":     "^IXIC",
        "DOW JONES":  "^DJI",
        "GOLD":       "GC=F",
        "CRUDE OIL":  "CL=F",
        "USD/INR":    "INR=X",
    }
    items = []
    for name, sym in symbols.items():
        try:
            hist  = yf.Ticker(sym).history(period="2d")
            if hist.empty:
                raise ValueError("no data")
            cur   = hist['Close'].iloc[-1]
            prev  = hist['Close'].iloc[-2] if len(hist) >= 2 else cur
            chg   = ((cur - prev) / prev) * 100
            arrow = "▲" if chg >= 0 else "▼"
            sign  = "+" if chg >= 0 else ""
            if name in ["GOLD", "CRUDE OIL"]:
                val = f"${cur:,.2f}"
            elif name == "USD/INR":
                val = f"₹{cur:.2f}"
            else:
                val = f"{cur:,.2f}"
            items.append(f"{name} &nbsp; {val} &nbsp; {arrow} {sign}{chg:.2f}%")
        except:
            items.append(f"{name} &nbsp; -- &nbsp; N/A")
    return items

# ================================================================
#  SHARED CSS + HAMBURGER
# ================================================================

SHARED_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'IBM Plex Mono', monospace; background: #000; color: #fff; padding-bottom: 60px; }
    #site-header { background: #000; border-bottom: 2px solid #ff6600; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
    #site-logo { font-size: 1.6em; font-weight: 700; color: #fff; letter-spacing: 3px; }
    #nav-drawer { position: fixed; top: 0; right: -260px; width: 240px; height: 100vh; background: #050505; border-left: 1px solid #1a1a1a; z-index: 999; padding: 20px 0; transition: right 0.25s ease; }
    #nav-drawer.open { right: 0; }
    #nav-drawer-header { display: flex; justify-content: space-between; align-items: center; padding: 0 20px 16px; border-bottom: 1px solid #1a1a1a; margin-bottom: 10px; }
    .drawer-link { display: block; padding: 14px 20px; color: #555; text-decoration: none; font-size: 0.80em; font-weight: 700; letter-spacing: 3px; border-bottom: 1px solid #0f0f0f; }
    .drawer-link:hover { color: #fff; background: #0a0a0a; }
    .drawer-link.active { color: #ff6600; }
    #nav-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 998; }
    #nav-overlay.open { display: block; }
    #ticker-bar { background: #fff; color: #000; font-size: 0.75em; font-weight: 700; padding: 5px 0; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #ddd; }
    #ticker-content { display: inline-block; animation: scroll-ticker 90s linear infinite; padding-left: 100%; }
    #ticker-content span { margin-right: 60px; color: #000; }
    @keyframes scroll-ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
    #main-content { max-width: 900px; margin: 30px auto; padding: 0 24px; }
    .page-title { font-size: 0.72em; color: #ff6600; letter-spacing: 3px; font-weight: 700; margin-bottom: 24px; padding-bottom: 10px; border-bottom: 1px solid #1a1a1a; }
    .placeholder-section { border: 1px solid #111; padding: 30px 20px; margin-bottom: 20px; }
    .placeholder-section h3 { font-size: 0.72em; color: #444; letter-spacing: 2px; margin-bottom: 10px; }
    .placeholder-section p { font-size: 0.74em; color: #2a2a2a; font-style: italic; }
    #bookmark-panel { position: fixed; top: 60px; right: 20px; width: 265px; max-height: 400px; background: #0a0a0a; border: 1px solid #1a1a1a; padding: 14px; overflow-y: auto; display: none; z-index: 999; }
    #bookmark-panel h3 { color: #ff6600; letter-spacing: 3px; font-size: 0.70em; border-bottom: 1px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 10px; }
    #bookmark-list li { font-size: 0.74em; color: #888; padding: 7px 0; cursor: pointer; border-bottom: 1px solid #0f0f0f; }
"""

SHARED_JS = """
    function toggleMenu() {
        document.getElementById('nav-drawer').classList.toggle('open');
        document.getElementById('nav-overlay').classList.toggle('open');
    }
    function togglePanel() {
        const p = document.getElementById('bookmark-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    }
    function showBookmarks() {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.getElementById('bookmark-toggle-drawer') && (document.getElementById('bookmark-toggle-drawer').innerHTML = bm.length > 0 ? 'SAVED ['+bm.length+']' : 'SAVED');
        document.getElementById('bookmark-list').innerHTML = bm.length === 0
            ? '<li style="color:#333;cursor:default;">No saved reports</li>'
            : bm.map(b => `<li>${b}</li>`).join('');
    }
    window.onload = function() { showBookmarks(); };
"""

def shared_header(active_page):
    pages = [
        ("index.html",   "HOME"),
        ("research.html","RESEARCH"),
        ("market.html",  "MARKET"),
        ("economy.html", "ECONOMY"),
    ]
    links = "".join(
        f'<a href="{url}" class="drawer-link{"  active" if name == active_page else ""}">{name}</a>'
        for url, name in pages
    )
    return f"""
    <div id="site-header">
        <div id="site-logo">{WEBSITE_TITLE}</div>
        <button id="hamburger" onclick="toggleMenu()" style="background:none;border:none;cursor:pointer;color:#888;font-size:1.4em;padding:0;line-height:1;">&#9776;</button>
    </div>
    <div id="nav-drawer">
        <div id="nav-drawer-header">
            <span style="color:#ff6600;font-size:0.75em;letter-spacing:3px;font-weight:700;">MENU</span>
            <button onclick="toggleMenu()" style="background:none;border:none;color:#444;cursor:pointer;font-size:1.2em;">&#10005;</button>
        </div>
        <nav id="drawer-nav">
            {links}
            <a href="#" class="drawer-link" onclick="togglePanel();toggleMenu();" id="bookmark-toggle-drawer">SAVED</a>
        </nav>
    </div>
    <div id="nav-overlay" onclick="toggleMenu()"></div>"""

# ================================================================
#  BUILD MARKET PAGE
# ================================================================

def build_market(ticker_items):
    today       = datetime.today().strftime('%d %B %Y')
    ticker_html = "".join(f'<span>{t}</span>' for t in ticker_items)
    header      = shared_header("MARKET")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{WEBSITE_TITLE} — Market</title>
    <style>{SHARED_CSS}</style>
</head>
<body>
    {header}
    <div id="ticker-bar">
        <div id="ticker-content">{ticker_html}{ticker_html}</div>
    </div>
    <div id="main-content">
        <div class="page-title">MARKET DASHBOARD</div>

        <div class="placeholder-section">
            <h3>FII / DII FLOW</h3>
            <p>Coming soon — 15-day FII/DII buy-sell data</p>
        </div>

        <div class="placeholder-section">
            <h3>BOND MARKET</h3>
            <p>Coming soon — 10Y yield, spread data</p>
        </div>

        <div class="placeholder-section">
            <h3>MARKET BREADTH</h3>
            <p>Coming soon — Advance/Decline, 52W high/low</p>
        </div>

        <div class="placeholder-section">
            <h3>GOLD & CRUDE</h3>
            <p>Coming soon — Monthly chart data</p>
        </div>

    </div>
    <div id="bookmark-panel">
        <h3>SAVED REPORTS</h3>
        <ul id="bookmark-list"></ul>
    </div>
    <script>{SHARED_JS}</script>
</body>
</html>"""

    with open("market.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("market.html ready!")


# ================================================================
#  MAIN
# ================================================================

print("Fetching ticker...")
ticker_items = fetch_ticker()
build_market(ticker_items)
print("Done!")