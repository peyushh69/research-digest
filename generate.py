# ============================================================
#  QUANTIS - RESEARCH DIGEST GENERATOR
#  How to run: python generate.py
#  What it does: reads PDFs from pdfs/ folder, builds index.html
#  Extracts: AI summary + key points + tables from each PDF
# ============================================================

import fitz
import pdfplumber
import os
import json
import yfinance as yf
from google import genai
from datetime import datetime


# ============================================================
#  *** PUT YOUR GEMINI API KEY HERE ***
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


# ============================================================
#  SECTION 1: PDF TEXT EXTRACTOR
#  DO NOT TOUCH — opens PDF and returns all text
# ============================================================

def pdf_se_text_nikalo(filepath):
    doc = fitz.open(filepath)
    poora_text = ""
    for page in doc:
        poora_text += page.get_text()
    doc.close()
    return poora_text


# ============================================================
#  SECTION 1B: PDF TITLE EXTRACTOR
#  Picks the first meaningful line from PDF as the report title
#  Falls back to cleaned filename if nothing good found
# ============================================================

TITLE_SKIP_WORDS = [
    'bloomberg', 'reuters', 'research is also available', 'nuvama',
    'systematix', 'edelweiss', 'motilal', 'kotak', 'hdfc securities',
    'icici', 'axis securities', 'disclaimer', 'confidential',
    'page', 'www', 'http', '@', 'tel:', 'fax:', 'mob:', 'phone:',
    'sebi', 'registered', 'member', 'bse', 'nse', 'india limited',
    'private limited', 'pvt ltd', 'kindly', 'please note',
    'unsubscribe', 'click here', 'terms', 'conditions',
    'investors are advised', 'refer disclosures', 'institutional equities',
    'pl capital', 'hsie', 'research report', 'equity research',
    'all rights reserved', 'copyright', 'for private circulation',
    'not for public', 'important disclosures',
    'sector rating', 'overweight', 'underweight', 'outperform',
    'rating:', 'coverage universe', 'price target',
]

def title_nikalo(text, filename):
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) < 25:
            continue
        if line[0].isdigit() and len(line) < 40:
            continue
        if any(word in line.lower() for word in TITLE_SKIP_WORDS):
            continue
        # Skip lines that are mostly punctuation or numbers
        alpha_count = sum(1 for c in line if c.isalpha())
        if alpha_count < 15:
            continue
        return line[:130]
    # Fallback: clean filename
    name = filename.replace('.pdf', '').replace('_', ' ').replace('+', ' ').replace('-', ' ')
    return name.title()


# ============================================================
#  SECTION 1C: SECTOR AUTO-DETECT
#  Detects sector from filename and first 1000 chars of content
# ============================================================

SECTOR_KEYWORDS = {
    'INFLATION':   ['wpi', 'cpi', 'inflation', 'price index', 'iip'],
    'ENERGY':      ['oil', 'gas', 'crude', 'opec', 'coal', 'renewable', 'ntpc', 'power', 'energy', 'strait', 'petroleum', 'refin', 'ongc', 'bpcl', 'iocl'],
    'BANKING':     ['bank', 'nbfc', 'rbi', 'credit', 'npa', 'deposit', 'loan', 'repo rate'],
    'TECHNOLOGY':  ['it services', 'software', 'saas', 'cloud', 'semiconductor', 'infosys', 'wipro', 'tcs', 'hcl tech'],
    'AUTO':        ['auto', 'vehicle', 'ev ', 'electric vehicle', 'passenger', 'two-wheeler', 'automobile', 'maruti', 'tata motors'],
    'PHARMA':      ['pharma', 'drug', 'fda', 'clinical', 'api ', 'hospital', 'healthcare', 'biotech'],
    'FMCG':        ['fmcg', 'consumer goods', 'food', 'beverage', 'rural demand', 'volume growth', 'hindustan unilever'],
    'REAL ESTATE': ['real estate', 'realty', 'housing', 'property', 'construction', 'cement'],
    'METALS':      ['steel', 'metal', 'aluminium', 'copper', 'iron ore', 'zinc'],
    'TELECOM':     ['telecom', 'arpu', 'subscriber', '5g', 'jio', 'airtel', 'spectrum'],
    'MARKETS':     ['nifty', 'sensex', 'equity', 'market outlook', 'index', 'valuation', 'fii', 'dii'],
    'ECONOMY':     ['gdp', 'fiscal', 'budget', 'trade deficit', 'current account', 'forex', 'rbi policy'],
    'GEOPOLITICS': ['geopolit', 'war', 'conflict', 'iran', 'israel', 'ukraine', 'russia', 'strategic'],
}

def sector_detect(text, filename):
    check_text = (filename + " " + text[:2000]).lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in check_text:
                return sector
    return 'RESEARCH'


# ============================================================
#  SECTION 1D: PDF TABLE EXTRACTOR
#  Uses pdfplumber to find tables inside PDFs
# ============================================================

def tables_nikalo(filepath, max_tables=2, min_rows=2, min_cols=2):
    extracted_tables = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    clean_table = []
                    for row in table:
                        clean_row = [str(cell).strip() if cell else "" for cell in row]
                        if any(cell for cell in clean_row):
                            clean_table.append(clean_row)
                    if len(clean_table) < min_rows:
                        continue
                    if len(clean_table[0]) < min_cols:
                        continue
                    extracted_tables.append(clean_table)
                    if len(extracted_tables) >= max_tables:
                        return extracted_tables
    except Exception as e:
        print(f"  Table extraction error: {e}")
    return extracted_tables


# ============================================================
#  SECTION 2: FILTER WORDS LIST
#  Lines containing these words are removed from key points
# ============================================================

FILTER_WORDS = [
    'disclaimer', 'views expressed', 'do not necessarily', 'reflect the views',
    'personal views', 'author', 'nothing contained', 'shall constitute',
    'solicitation', 'offer to sell', 'offer to purchase',
    'invitation or solicitation', 'any entity', 'accuracy', 'completeness',
    'reliability', 'representation', 'also available', 'bloomberg', 'reuters',
    'factset', 'research is also', 'nuvama research', 'systematix', 'edelweiss',
    'motilal oswal', 'kotak securities', 'hdfc securities', 'sebi registered',
    'unsubscribe', 'click here', 'kindly note', 'tel:', 'mob:', 'fax:',
    'all rights reserved', 'copyright', 'terms of use', 'privacy policy',
    # Promotional / non-insight content
    'we hosted', 'webinar', 'founder', 'ceo', 'chief ', 'years of experience',
    'ex-rystad', 'ex-shell', 'xanalyst', 'our analyst', 'we believe investors',
    'we recommend', 'investors are advised',
    # Stock tips / broker ratings
    'buy rating', 'sell rating', 'hold rating', 'strong buy', 'target price',
    'price target', 'accumulate', 'sector rating', 'overweight', 'underweight',
    'outperform', 'underperform', 'coverage universe',
]


# ============================================================
#  SECTION 3: GEMINI AI SUMMARIZATION
#  Sends PDF text to Gemini API and returns a clean summary
# ============================================================

def gemini_summary(text, filename):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""You are a financial journalist writing for an economics and markets intelligence platform — NOT a broker or stock advisor.

Read this research report and write a crisp 2-3 sentence insight about what is happening in this sector or economy.

STRICT RULES:
- Focus on the MACRO trend, sector development, or economic event — NOT stock picks
- Do NOT mention any stock ratings (BUY/SELL/HOLD/Overweight etc.)
- Do NOT recommend any stocks or say which company to invest in
- DO mention specific data points, % changes, macro drivers if available
- End with WHY this matters for the Indian economy or markets broadly
- Write like an economist or journalist, not a broker
- Maximum 60 words

Report filename: {filename}
Report text:
{text[:4000]}

Insight:"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"  Gemini API error: {e}")
        return None


# ============================================================
#  SECTION 3B: KEY POINTS EXTRACTOR (fallback if Gemini fails)
# ============================================================

def key_points_nikalo(text, kitne_points=4):
    min_line_length = 60
    max_line_length = 200

    clean_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if '@' in line:
            continue
        if len(line) < min_line_length or len(line) > max_line_length:
            continue
        if any(word in line.lower() for word in FILTER_WORDS):
            continue
        alpha_count = sum(1 for c in line if c.isalpha())
        if alpha_count < 30:
            continue
        clean_lines.append(line)

    # Return top lines as bullet points (simple extraction)
    seen = set()
    unique_lines = []
    for line in clean_lines:
        key = line[:40].lower()
        if key not in seen:
            seen.add(key)
            unique_lines.append(line)
        if len(unique_lines) >= kitne_points:
            break

    return unique_lines if unique_lines else ["Report processed. Open PDF for full details."]


# ============================================================
#  SECTION 4: LIVE TICKER DATA FROM YFINANCE
#  Fetches real-time market data when you run generate.py
# ============================================================

def fetch_ticker_data():
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

    ticker_items = []
    print("Fetching live market data...")

    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if hist.empty or len(hist) < 1:
                raise ValueError("No data")

            current = hist['Close'].iloc[-1]
            prev    = hist['Close'].iloc[-2] if len(hist) >= 2 else current
            change  = ((current - prev) / prev) * 100
            arrow   = "▲" if change >= 0 else "▼"
            sign    = "+" if change >= 0 else ""

            # Format values
            if name in ["GOLD", "CRUDE OIL"]:
                val_str = f"${current:,.2f}"
            elif name == "USD/INR":
                val_str = f"₹{current:.2f}"
            elif name in ["NIFTY 50", "SENSEX", "BANK NIFTY"]:
                val_str = f"{current:,.2f}"
            else:
                val_str = f"{current:,.2f}"

            ticker_items.append(
                f"{name} &nbsp; {val_str} &nbsp; {arrow} {sign}{change:.2f}%"
            )
            print(f"  {name}: {val_str} {arrow} {sign}{change:.2f}%")

        except Exception as e:
            print(f"  Could not fetch {name} ({symbol}): {e}")
            # Fallback hardcoded value
            ticker_items.append(f"{name} &nbsp; -- &nbsp; N/A")

    return ticker_items


# ============================================================
#  SECTION 5: WEBSITE TITLE
# ============================================================

WEBSITE_TITLE = "Quantis"


# ============================================================
#  SECTION 6: WEBSITE DESIGN (CSS)
#  - Ticker bar: WHITE background, black text
#  - SAVED button: white background, black text
#  - Header: black background, orange border
#  - Title: bold white, date left, orange sector tag right
# ============================================================

WEBSITE_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');

    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }

    body {
        font-family: 'IBM Plex Mono', monospace;
        background: #000000;
        color: #ffffff;
        padding-bottom: 60px;
    }

    /* ---- BLOOMBERG STYLE HEADER ---- */
    #site-header {
        background: #000000;
        border-bottom: 2px solid #ff6600;
        padding: 14px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 100;
    }

    #site-logo {
        font-size: 1.6em;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: 3px;
        text-transform: uppercase;
    }

    /* ---- SAVED BUTTON — DIM GREY THEME ---- */
    #bookmark-toggle {
        background: #2a2a2a;
        border: 1px solid #444444;
        color: #aaaaaa;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75em;
        font-weight: 700;
        padding: 6px 14px;
        cursor: pointer;
        letter-spacing: 2px;
    }

    #bookmark-toggle:hover {
        background: #333333;
        color: #ffffff;
    }

    /* ---- TICKER BAR — WHITE THEME ---- */
    #ticker-bar {
        background: #ffffff;
        color: #000000;
        font-size: 0.75em;
        font-weight: 700;
        padding: 5px 0;
        overflow: hidden;
        white-space: nowrap;
        border-bottom: 1px solid #dddddd;
    }

    #ticker-content {
        display: inline-block;
        animation: scroll-ticker 90s linear infinite;
        padding-left: 100%;
    }

    #ticker-content span {
        margin-right: 60px;
        letter-spacing: 1px;
        color: #000000;
    }

    @keyframes scroll-ticker {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }

    /* ---- MAIN CONTENT AREA ---- */
    #main-content {
        max-width: 960px;
        margin: 30px auto;
        padding: 0 24px;
    }

    /* ---- REPORT CARD ---- */
    .report-card {
        background: #000000;
        border: none;
        border-bottom: 1px solid #222222;
        padding: 24px 0;
        margin: 0;
    }

    /* ---- REPORT TITLE ---- */
    .report-card h2 {
        font-size: 1.15em;
        color: #ffffff;
        text-transform: none;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        font-weight: 700;
        line-height: 1.4;
    }

    /* ---- TITLE META ROW: date left, sector tag right ---- */
    .title-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
    }

    .date {
        font-size: 0.72em;
        color: #888888;
        letter-spacing: 1px;
    }

    .sector-tag {
        font-size: 0.68em;
        font-weight: 700;
        color: #000000;
        background: #ff6600;
        padding: 3px 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    /* ---- AI SUMMARY BOX ---- */
    .ai-summary {
        background: #0a0a0a;
        border-left: 3px solid #ff6600;
        padding: 10px 14px;
        margin-bottom: 14px;
        font-size: 0.83em;
        color: #cccccc;
        line-height: 1.7;
        font-style: italic;
    }

    /* ---- BULLET POINTS ---- */
    ul {
        line-height: 1.8;
        padding-left: 18px;
    }

    li {
        margin-bottom: 8px;
        color: #dddddd;
        font-size: 0.88em;
        padding-bottom: 6px;
        border-bottom: 1px solid #111111;
    }

    li::marker {
        color: #ff6600;
    }

    /* ---- TABLE STYLES — COMPACT ---- */
    .pdf-table-wrap {
        margin: 12px 0;
        overflow-x: auto;
    }

    .table-description {
        font-size: 0.68em;
        color: #666666;
        margin-bottom: 5px;
        letter-spacing: 0.5px;
        font-style: italic;
    }

    .pdf-table {
        width: auto;
        max-width: 100%;
        border-collapse: collapse;
        font-size: 0.70em;
        color: #bbbbbb;
    }

    .pdf-table tr:first-child td {
        background: #1a0a00;
        color: #ff6600;
        font-weight: 700;
        padding: 5px 8px;
        border-bottom: 1px solid #ff6600;
        text-align: left;
        letter-spacing: 0.3px;
        white-space: nowrap;
    }

    .pdf-table tr:not(:first-child) td {
        padding: 4px 8px;
        border-bottom: 1px solid #111111;
        text-align: left;
        vertical-align: top;
        white-space: nowrap;
    }

    .pdf-table tr:nth-child(even) td {
        background: #0a0a0a;
    }

    /* ---- CARD FOOTER ---- */
    .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 14px;
        padding-top: 8px;
    }

    /* ---- BOOKMARK PANEL ---- */
    #bookmark-panel {
        position: fixed;
        top: 90px;
        right: 20px;
        width: 280px;
        max-height: 420px;
        background: #0d0d0d;
        border: 1px solid #333333;
        padding: 16px;
        overflow-y: auto;
        display: none;
        z-index: 999;
        border-radius: 4px;
    }

    #bookmark-panel h3 {
        color: #ff6600;
        letter-spacing: 3px;
        font-size: 0.75em;
        border-bottom: 1px solid #333333;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }

    #bookmark-list li {
        font-size: 0.78em;
        line-height: 1.5;
        color: #cccccc;
        border-bottom: 1px solid #1a1a1a;
        padding: 8px 0;
        cursor: pointer;
        letter-spacing: 0.3px;
        border: none;
        margin-bottom: 0;
    }

    #bookmark-list li:hover {
        color: #ffffff;
    }
"""


# ============================================================
#  SECTION 7: JAVASCRIPT — BOOKMARKS + READ MORE
# ============================================================

BOOKMARK_JS = """
    function toggleBookmark(btn, text) {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const index = bookmarks.indexOf(text);
        if (index === -1) {
            bookmarks.push(text);
            btn.style.color = '#ff6600';
            btn.title = 'Saved!';
        } else {
            bookmarks.splice(index, 1);
            btn.style.color = '#333';
            btn.title = 'Bookmark this report';
        }
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        showBookmarks();
    }

    function showBookmarks() {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const list = document.getElementById('bookmark-list');
        const btn = document.getElementById('bookmark-toggle');
        list.innerHTML = bookmarks.length === 0
            ? '<li style="color:#555; cursor:default; padding:8px 0;">No saved reports</li>'
            : bookmarks.map((b, i) => `
                <li onclick="scrollToReport('${b}')" title="Go to report">
                    ${b}
                    <span onclick="event.stopPropagation(); removeBookmark(${i})"
                          style="cursor:pointer; color:#555; float:right; margin-left:8px;">[X]</span>
                </li>`).join('');
        btn.innerHTML = bookmarks.length > 0 ? 'SAVED [' + bookmarks.length + ']' : 'SAVED';
    }

    function scrollToReport(title) {
        const cards = document.querySelectorAll('.report-card');
        cards.forEach(card => {
            const h2 = card.querySelector('h2');
            if (h2 && h2.innerText.toLowerCase().includes(title.toLowerCase().slice(0, 20))) {
                card.scrollIntoView({ behavior: 'smooth', block: 'start' });
                togglePanel();
            }
        });
    }

    function togglePanel() {
        const panel = document.getElementById('bookmark-panel');
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }

    function removeBookmark(index) {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        bookmarks.splice(index, 1);
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        showBookmarks();
        markSavedButtons();
    }

    function markSavedButtons() {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.querySelectorAll('.bookmark-btn').forEach(btn => {
            const text = btn.getAttribute('data-text');
            btn.style.color = bookmarks.includes(text) ? '#ff6600' : '#333';
        });
    }

    function toggleMore(i, btn) {
        const section = document.getElementById('more-' + i);
        if (section.style.display === 'none') {
            section.style.display = 'block';
            btn.innerHTML = 'READ LESS &#9650;';
        } else {
            section.style.display = 'none';
            btn.innerHTML = 'READ MORE &#9660;';
        }
    }

    window.onload = function() {
        showBookmarks();
        markSavedButtons();
    };
"""


# ============================================================
#  SECTION 8: HTML TABLE BUILDER
# ============================================================

BUY_SELL_WORDS = ['buy', 'sell', 'hold', 'accumulate', 'overweight', 'underweight', 'outperform', 'underperform', 'neutral', 'reduce']

def table_description_generate(table, sector):
    """Generate a one-line description of what the table shows"""
    headers = [str(cell).lower() for cell in table[0] if cell]
    header_str = " ".join(headers)

    if any(w in header_str for w in ['cmp', 'reco', 'tp', 'target', 'rating', 'mkt cap']):
        return f"Valuation & coverage data for key {sector} sector companies"
    elif any(w in header_str for w in ['fy', 'revenue', 'ebitda', 'pat', 'eps', 'profit']):
        return f"Financial estimates for {sector} sector companies"
    elif any(w in header_str for w in ['inflation', 'wpi', 'cpi', 'index', 'iip']):
        return f"Key economic indicators — {sector} data"
    elif any(w in header_str for w in ['country', 'global', 'world', 'region']):
        return f"Global comparison data relevant to {sector}"
    else:
        return f"Data extracted from report — {sector} sector"

def filter_buy_sell_rows(table):
    """Remove rows that are purely stock recommendation data"""
    filtered = []
    for i, row in enumerate(table):
        if i == 0:
            filtered.append(row)
            continue
        row_text = " ".join(str(cell).lower() for cell in row if cell)
        # Skip rows where most content is buy/sell/hold recommendations
        buy_sell_count = sum(1 for w in BUY_SELL_WORDS if w in row_text.split())
        if buy_sell_count >= 2:
            continue
        filtered.append(row)
    return filtered if len(filtered) > 1 else table

def table_to_html(table, sector='RESEARCH'):
    # Filter buy/sell rows
    table = filter_buy_sell_rows(table)
    description = table_description_generate(table, sector)

    rows_html = ""
    for row in table:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        rows_html += f"<tr>{cells}</tr>\n"
    return f"""
    <div class="pdf-table-wrap">
        <div class="table-description">{description}</div>
        <table class="pdf-table">
            {rows_html}
        </table>
    </div>"""


# ============================================================
#  SECTION 9: HTML PAGE BUILDER
#  Assembles everything into the final website
#
#  CARD LAYOUT:
#  [Report Title — bold white]
#  [Published: date left]  [SECTOR TAG right — orange]
#  [AI Summary box — italic, left orange border]
#  - Bullet point 1 (always visible)
#  - Bullet point 2 (always visible)
#  [Tables from PDF]
#  [Hidden points on READ MORE]
#  [Bookmark icon left]  [READ MORE right]
# ============================================================

def website_banao(reports_data, ticker_items):
    aaj_ki_tarikh = datetime.today().strftime('%d %B %Y')
    ticker_html = "".join(f'<span>{item}</span>' for item in ticker_items)

    all_cards = ""

    for i, report in enumerate(reports_data):
        visible_points = report['points'][:2]
        hidden_points = report['points'][2:]

        visible_html = "".join(f"            <li>{p}</li>\n" for p in visible_points)
        hidden_html = "".join(f"            <li>{p}</li>\n" for p in hidden_points)

        # Tables HTML
        tables_html = ""
        if report.get('tables'):
            for table in report['tables']:
                tables_html += table_to_html(table, report.get('sector', 'RESEARCH'))

        # Hidden section
        hidden_section = ""
        if hidden_points:
            hidden_section = f"""
        <ul id="more-{i}" style="display:none; padding-left:18px; margin-top:0;">
{hidden_html}        </ul>"""

        # AI Summary box
        summary_html = ""
        if report.get('summary'):
            summary_html = f'<div class="ai-summary">{report["summary"]}</div>'

        safe_title = report['title'].replace("'", "").replace('"', '')
        sector = report.get('sector', 'RESEARCH')

        all_cards += f"""
    <div class="report-card">
        <h2>{report['title']}</h2>
        <div class="title-meta">
            <span class="date">Published: {aaj_ki_tarikh}</span>
            <span class="sector-tag">{sector}</span>
        </div>

        {summary_html}

        <ul>
{visible_html}        </ul>

        {tables_html}

        {hidden_section}

        <div class="card-footer">
            <button class="bookmark-btn"
                    data-text="{safe_title}"
                    title="Bookmark this report"
                    onclick="toggleBookmark(this, '{safe_title}')"
                    style="background:none; border:none; cursor:pointer;
                           color:#333; padding:0;">
                <svg width="12" height="16" viewBox="0 0 14 18" fill="currentColor">
                    <path d="M0 0h14v18l-7-4.5L0 18z"/>
                </svg>
            </button>

            <button onclick="toggleMore({i}, this)"
                    style="background:none; border:none; cursor:pointer;
                           color:#666666; font-family:inherit; font-size:0.78em;
                           letter-spacing:2px; text-transform:uppercase;">
                READ MORE &#9660;
            </button>
        </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{WEBSITE_TITLE}</title>
    <style>
{WEBSITE_CSS}
    </style>
</head>
<body>

    <div id="site-header">
        <div id="site-logo">{WEBSITE_TITLE}</div>
        <button id="bookmark-toggle" onclick="togglePanel()">SAVED</button>
    </div>

    <div id="ticker-bar">
        <div id="ticker-content">
            {ticker_html}
            {ticker_html}
        </div>
    </div>

    <div id="main-content">
        {all_cards}
    </div>

    <div id="bookmark-panel">
        <h3>SAVED REPORTS</h3>
        <ul id="bookmark-list"></ul>
    </div>

    <script>
{BOOKMARK_JS}
    </script>

</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html updated successfully!")


# ============================================================
#  SECTION 10: MAIN PROCESS
#  Scans pdfs/ folder, processes new PDFs only
#  Newest reports appear FIRST
# ============================================================

pdf_folder = "pdfs"
processed_file = "processed.json"

if os.path.exists(processed_file):
    with open(processed_file, "r") as f:
        processed_data = json.load(f)
else:
    processed_data = {}

new_found = False

for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf") and filename not in processed_data:
        print(f"\nNew PDF found, processing: {filename}")
        filepath = os.path.join(pdf_folder, filename)

        text   = pdf_se_text_nikalo(filepath)
        title  = title_nikalo(text, filename)
        sector = sector_detect(text, filename)
        points = key_points_nikalo(text)
        tables = tables_nikalo(filepath)

        print(f"  Title:  {title[:80]}...")
        print(f"  Sector: {sector}")

        # Gemini AI Summary
        print(f"  Generating AI summary...")
        summary = gemini_summary(text, filename)
        if summary:
            print(f"  Summary: {summary[:80]}...")
        else:
            print(f"  Summary: Gemini unavailable, using bullet points only")

        if tables:
            print(f"  Found {len(tables)} table(s)")
        else:
            print(f"  No tables found")

        processed_data[filename] = {
            'title':   title,
            'sector':  sector,
            'summary': summary,
            'points':  points,
            'tables':  tables
        }
        new_found = True

if new_found:
    with open(processed_file, "w") as f:
        json.dump(processed_data, f, indent=2)
    print("\nNew PDF(s) processed and saved!")
else:
    print("No new PDFs found.")

# Fetch live ticker data
ticker_items = fetch_ticker_data()

# Build website
website_banao(list(reversed(list(processed_data.values()))), ticker_items)
print("Website updated successfully!")