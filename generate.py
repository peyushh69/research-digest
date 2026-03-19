# ================================================================
#  QUANTIS — RESEARCH DIGEST GENERATOR
#  
#  Yeh file kya karti hai:
#  1. pdfs/ folder se PDFs padhti hai
#  2. Har PDF se title, bullet points, summary, tables nikalti hai
#  3. Gemini AI se smart summaries banati hai
#  4. Live market data (Nifty, Sensex etc.) fetch karti hai
#  5. Sab kuch ek website (index.html) mein daalti hai
#
#  Kaise chalayein:
#  Terminal mein likho:  python generate.py
#
#  Zaruri folders:
#  - pdfs/          ← apni PDF files yahan rakho
#  - .env           ← API key yahan honi chahiye
#  - processed.json ← automatically banta hai, delete karo toh sab reprocess hoga
# ================================================================


# ================================================================
#  LIBRARIES — yeh sab install honi chahiye
#  Install karne ke liye: pip install pymupdf pdfplumber yfinance google-genai python-dotenv
# ================================================================

import fitz          # PyMuPDF — PDF se text nikalne ke liye
import pdfplumber    # PDF se tables nikalne ke liye
import os            # File system ke liye
import json          # Data save/load ke liye
import yfinance as yf               # Live market data ke liye
from google import genai            # Gemini AI ke liye
from datetime import datetime       # Aaj ki date ke liye
from dotenv import load_dotenv      # .env file se API key load karne ke liye


# ================================================================
#  STEP 1: API KEY SETUP
#
#  API key .env file se automatically load hoti hai
#  .env file mein yeh hona chahiye:
#  GEMINI_API_KEY=AIzaSy...tumhari_key_yahan
#
#  KABHI BHI yahan seedha key mat likho — woh GitHub pe public ho jaayegi!
# ================================================================

load_dotenv()  # .env file load karo

# GOOGLE_API_KEY conflict fix — agar purani key system mein set hai toh remove karo
# Warna Gemini dono keys dekh ke confuse hota hai
os.environ.pop("GOOGLE_API_KEY", None)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
WEBSITE_TITLE  = "Quantis"


# ================================================================
#  STEP 2: GEMINI AI HELPER
#
#  Yeh function Gemini API ko call karta hai
#  Har jagah se — title, bullets, summary, table description —
#  sab is ek function se jaata hai
#
#  Agar API key galat hai ya internet nahi hai toh None return karega
# ================================================================

def gemini(prompt):
    try:
        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model    = "gemini-2.0-flash",
            contents = prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"  [Gemini error] {e}")
        return None


# ================================================================
#  STEP 3: PDF SE TEXT NIKALO
#
#  PyMuPDF library se PDF ka poora text ek string mein nikalte hain
#  Yeh text baad mein Gemini ko bheja jaata hai
# ================================================================

def pdf_text(filepath):
    doc  = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


# ================================================================
#  STEP 4: AI TITLE GENERATOR
#
#  Gemini PDF ka text padh ke ek clean headline banata hai
#  Jaise: "India WPI Inflation Hits 11-Month High in February"
#
#  Kya NAHI aana chahiye title mein:
#  - Broker ka naam (Nuvama, Systematix etc.)
#  - BUY/SELL/HOLD ratings
#  - Analyst ka naam
#
#  Agar Gemini fail kare toh filename se title banta hai (fallback)
# ================================================================

def ai_title(text, filename):
    result = gemini(f"""You are a financial news editor. Write a single crisp headline for this research report.

Rules:
- Maximum 10 words
- Focus on the KEY economic event, sector trend, or macro development
- Do NOT mention: broker name, BUY/SELL/HOLD ratings, stock tips, analyst names
- Style: Economic Times or Bloomberg headline
- No quotes, no full stop at end

Filename: {filename}
Report (first 1500 chars): {text[:1500]}

Headline (just the text, nothing else):""")

    # Agar Gemini ne sahi jawab diya toh use karo
    if result and len(result) > 10:
        return result[:130]

    # Fallback: filename ko clean karke title banao
    name = filename.replace('.pdf','').replace('_',' ').replace('+',' ').replace('-',' ')
    return name.title()[:130]


# ================================================================
#  STEP 5: SECTOR AUTO-DETECT
#
#  PDF ke filename aur content se automatically sector detect hota hai
#  Jaise: "oil", "gas", "crude" → ENERGY sector
#         "bank", "rbi", "credit" → BANKING sector
#
#  Agar koi match nahi mila toh "RESEARCH" return hoga
# ================================================================

SECTOR_MAP = {
    'INFLATION':   ['wpi', 'cpi', 'inflation', 'price index', 'iip'],
    'ENERGY':      ['oil', 'gas', 'crude', 'opec', 'ntpc', 'power', 'energy', 'petroleum', 'ongc', 'bpcl', 'strait'],
    'BANKING':     ['bank', 'nbfc', 'rbi', 'credit', 'npa', 'deposit', 'loan', 'repo rate'],
    'TECHNOLOGY':  ['it services', 'software', 'saas', 'cloud', 'infosys', 'wipro', 'tcs', 'hcl tech'],
    'AUTO':        ['automobile', 'auto sector', 'vehicle sales', 'ev ', 'maruti', 'tata motors'],
    'PHARMA':      ['pharma', 'drug', 'fda', 'clinical', 'healthcare', 'biotech'],
    'FMCG':        ['fmcg', 'consumer goods', 'food inflation', 'rural demand'],
    'REAL ESTATE': ['real estate', 'realty', 'housing', 'property', 'cement'],
    'METALS':      ['steel', 'metal', 'aluminium', 'copper', 'iron ore', 'zinc'],
    'TELECOM':     ['telecom', 'arpu', '5g', 'jio', 'airtel', 'spectrum'],
    'MARKETS':     ['nifty', 'sensex', 'equity market', 'market outlook', 'fii', 'dii'],
    'ECONOMY':     ['gdp', 'fiscal', 'budget', 'trade deficit', 'current account', 'rbi policy'],
    'GEOPOLITICS': ['geopolit', 'war', 'conflict', 'iran', 'israel', 'ukraine', 'russia'],
}

def detect_sector(text, filename):
    # Filename + report ke pehle 2000 characters mein keywords dhundho
    check = (filename + " " + text[:2000]).lower()
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in check:
                return sector
    return 'RESEARCH'  # Koi match nahi mila


# ================================================================
#  STEP 6: AI BULLET POINTS GENERATOR
#
#  Gemini 4 crisp economic facts likhta hai
#
#  BILKUL NAHI AANA CHAHIYE:
#  - BUY / SELL / HOLD / Accumulate / Overweight
#  - Target Price / CMP / Price Target
#  - Broker names / Analyst promotion
#  - Webinar / CEO / "30 years experience" wali lines
#
#  Double protection hai:
#  1. Gemini ko prompt mein strictly mana hai
#  2. Post-processing filter — agar Gemini bhool ke bhi likh de toh remove
# ================================================================

# Yeh words bullet points mein aane par line automatically remove ho jaayegi
STOCK_TIP_WORDS = [
    'buy', 'sell', 'hold', 'accumulate', 'overweight', 'underweight',
    'outperform', 'underperform', 'target price', 'price target', 'cmp',
    'strong buy', 'strong sell', 'reco', 'initiating coverage',
    'we recommend', 'our top pick', 'preferred pick',
]

def ai_bullets(text, sector):
    result = gemini(f"""Write exactly 4 bullet points summarizing key ECONOMIC or SECTOR facts from this report.

ABSOLUTE RULES — no exceptions:
- ZERO stock recommendations (no BUY, SELL, HOLD, Accumulate, Overweight, Target Price, CMP)
- ZERO broker/analyst names or promotional content
- Each bullet = one economic fact, data point, or sector trend with numbers if available
- Max 18 words per bullet
- Output: just 4 plain lines, no bullet symbols, no numbering

Sector: {sector}
Report text: {text[:5000]}

4 facts (plain lines only):""")

    if result:
        lines = [l.strip().lstrip('-*+.1234567890) ') for l in result.split('\n') if l.strip()]
        lines = [l for l in lines if len(l) > 15]
        # Post-processing filter — stock tip wali lines hatao
        lines = [l for l in lines if not any(w in l.lower() for w in STOCK_TIP_WORDS)]
        return lines[:4] if lines else ["Key economic data available in the original report."]
    return ["Key economic data available in the original report."]


# ================================================================
#  STEP 7: AI SUMMARY GENERATOR
#
#  Card ke neeche ek chhoti italic summary dikhti hai
#  Yeh batati hai ki report kya kehna chahti hai — plain language mein
#  Maximum 400 characters, 2 sentences
#
#  Koi stock tips nahi, koi ratings nahi — sirf economic story
# ================================================================

def ai_summary(text, sector, filename):
    result = gemini(f"""Write a short 2-sentence plain-language summary of what this research report is about.

Rules:
- Explain the economic/sector story in simple terms
- No stock tips, no ratings (BUY/SELL/HOLD), no broker language
- End with why this matters for India's economy or this sector
- Maximum 55 words total

Sector: {sector}
Filename: {filename}
Report: {text[:3000]}

Summary:""")
    return result[:400] if result else None


# ================================================================
#  STEP 8: TABLE EXTRACTION + CLEANING
#
#  pdfplumber library se PDF mein se tables nikalte hain
#
#  Kya filter hota hai:
#  1. Pure recommendation tables — jisme sirf Company/Rating/Target ho → SKIP (show hi nahi hogi)
#  2. BUY/SELL/HOLD columns → REMOVE (column hi hata dete hain)
#
#  Maximum 2 tables per PDF dikhayenge
# ================================================================

# Yeh words column mein zyada hone pe woh column remove ho jaayega
RATING_WORDS   = {'buy','sell','hold','accumulate','overweight','underweight',
                  'outperform','underperform','neutral','reduce','add'}

# Yeh column headers hote hain jisme rating data hota hai
RATING_HEADERS = {'reco','rating','recommendation','call','stance','view','recom','tp'}

def is_recommendation_table(table):
    """Check karo ki poori table sirf stock recommendations ki hai — agar haan toh skip karo"""
    if not table or not table[0]:
        return False
    headers   = [str(c).lower().strip() for c in table[0] if c]
    rec_count = sum(1 for h in headers if h in RATING_HEADERS or 'target' in h)
    return rec_count >= 2  # 2 ya zyada rating columns hain toh pure rec table hai

def remove_rating_columns(table):
    """Table se BUY/SELL/HOLD wale columns hata do"""
    if not table or not table[0]:
        return table

    remove = set()

    # Header se pehchano
    for ci, cell in enumerate(table[0]):
        if str(cell).lower().strip() in RATING_HEADERS:
            remove.add(ci)

    # Column ke values se pehchano — agar 40% se zyada values rating words hain
    if len(table) > 2:
        for ci in range(len(table[0])):
            vals = [str(table[ri][ci]).lower().strip()
                    for ri in range(1, min(len(table), 8))
                    if ci < len(table[ri])]
            if vals and sum(1 for v in vals if v in RATING_WORDS) / len(vals) > 0.4:
                remove.add(ci)

    if not remove:
        return table  # Kuch remove nahi karna

    # Remove kiye bina wali columns wapas banao
    return [[c for ci, c in enumerate(row) if ci not in remove] for row in table]

def tables_nikalo(filepath):
    """PDF se tables nikalo, clean karo, aur return karo"""
    extracted = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    if not table:
                        continue

                    # Empty rows hatao
                    clean = [[str(c).strip() if c else "" for c in row]
                             for row in table if any(c for c in row)]

                    # Bahut choti tables skip karo
                    if len(clean) < 2 or len(clean[0]) < 2:
                        continue

                    # Pure recommendation table → skip
                    if is_recommendation_table(clean):
                        print(f"  Skipped recommendation table")
                        continue

                    # Rating columns remove karo
                    clean = remove_rating_columns(clean)
                    extracted.append(clean)

                    # Maximum 2 tables per PDF
                    if len(extracted) >= 2:
                        return extracted

    except Exception as e:
        print(f"  [Table error] {e}")

    return extracted

def ai_table_description(table, sector):
    """Gemini table ke liye ek line description likhta hai"""
    preview = "\n".join(" | ".join(str(c) for c in row) for row in table[:4])
    result  = gemini(f"""Look at this table from a financial research report.
Write ONE sentence (max 12 words) describing what DATA/METRICS this table shows.
Focus on the numbers shown, not any recommendations.

Sector: {sector}
Table preview:
{preview}

One sentence description:""")
    return result if result else f"Key metrics — {sector} sector"


# ================================================================
#  STEP 9: LIVE MARKET DATA (TICKER BAR)
#
#  yfinance library se live data fetch karta hai
#  Yeh data website ke upar wali scrolling bar mein dikhta hai
#
#  Data fetch hota hai: Nifty, Sensex, Bank Nifty, S&P 500,
#  Nasdaq, Dow Jones, Gold, Crude Oil, USD/INR
#
#  Agar data nahi mila toh "N/A" dikhata hai
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
    print("Fetching live market data...")

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

            # Format — Gold/Crude mein $ sign, INR mein ₹
            if name in ["GOLD", "CRUDE OIL"]:
                val = f"${cur:,.2f}"
            elif name == "USD/INR":
                val = f"₹{cur:.2f}"
            else:
                val = f"{cur:,.2f}"

            items.append(f"{name} &nbsp; {val} &nbsp; {arrow} {sign}{chg:.2f}%")
            print(f"  {name}: {val} {arrow} {sign}{chg:.2f}%")

        except Exception as e:
            print(f"  Could not fetch {name}: {e}")
            items.append(f"{name} &nbsp; -- &nbsp; N/A")

    return items


# ================================================================
#  STEP 10: WEBSITE CSS (DESIGN)
#
#  Yahan sirf colors aur fonts hain — content nahi
#
#  Current design:
#  - Background: Black (#000000)
#  - Accent: Orange (#ff6600)
#  - Font: IBM Plex Mono
#  - Ticker bar: White background, black text
#  - SAVED button: Dark grey (aankhon ko bright nahi lagta)
#  - Sector tag: Orange background, black text
#  - AI Summary: Italic, grey, left border
# ================================================================

WEBSITE_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        font-family: 'IBM Plex Mono', monospace;
        background: #000;
        color: #fff;
        padding-bottom: 60px;
    }

    /* ---- HEADER (QUANTIS logo + SAVED button) ---- */
    #site-header {
        background: #000;
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
        color: #fff;
        letter-spacing: 3px;
    }

    /* SAVED button — dark grey, aankhon ko suit karta hai */
    #bookmark-toggle {
        background: #1a1a1a;
        border: 1px solid #444;
        color: #888;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75em;
        font-weight: 700;
        padding: 6px 14px;
        cursor: pointer;
        letter-spacing: 2px;
    }
    #bookmark-toggle:hover { background: #2a2a2a; color: #fff; }

    /* ---- TICKER BAR (scrolling market data) ---- */
    /* White background, black text — clean readable */
    #ticker-bar {
        background: #fff;
        color: #000;
        font-size: 0.75em;
        font-weight: 700;
        padding: 5px 0;
        overflow: hidden;
        white-space: nowrap;
        border-bottom: 1px solid #ddd;
    }
    #ticker-content {
        display: inline-block;
        /* 90 seconds mein ek loop — slow aur readable */
        animation: scroll-ticker 90s linear infinite;
        padding-left: 100%;
    }
    #ticker-content span { margin-right: 60px; color: #000; }
    @keyframes scroll-ticker {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }

    /* ---- MAIN CONTENT AREA ---- */
    #main-content { max-width: 900px; margin: 30px auto; padding: 0 24px; }

    /* ---- REPORT CARD ---- */
    .report-card { border-bottom: 1px solid #1a1a1a; padding: 28px 0; }

    /* ---- TITLE ---- */
    .report-card h2 {
        font-size: 1.1em;
        color: #fff;
        font-weight: 700;
        line-height: 1.5;
        margin-bottom: 8px;
    }

    /* ---- DATE (left) + SECTOR TAG (right) ---- */
    .title-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    .date { font-size: 0.68em; color: #555; letter-spacing: 1px; }
    .sector-tag {
        font-size: 0.65em;
        font-weight: 700;
        color: #000;
        background: #ff6600;
        padding: 3px 10px;
        letter-spacing: 2px;
    }

    /* ---- BULLET POINTS ---- */
    .bullets { padding-left: 16px; margin-bottom: 16px; }
    .bullets li {
        font-size: 0.84em;
        color: #bbb;
        line-height: 1.7;
        padding-bottom: 6px;
        margin-bottom: 4px;
        border-bottom: 1px solid #0f0f0f;
    }
    .bullets li::marker { color: #ff6600; }

    /* ---- TABLE ---- */
    .table-wrap { margin: 14px 0; overflow-x: auto; border: 1px solid #111; }
    .table-label {
        font-size: 0.63em;
        color: #555;
        font-style: italic;
        padding: 6px 10px 5px;
        border-bottom: 1px solid #111;
        letter-spacing: 0.3px;
    }
    .pdf-table { width: 100%; border-collapse: collapse; font-size: 0.67em; }
    /* Header row — orange text */
    .pdf-table tr:first-child td {
        background: #0d0600;
        color: #ff6600;
        font-weight: 700;
        padding: 6px 10px;
        border-bottom: 1px solid #ff6600;
        white-space: nowrap;
    }
    /* Data rows */
    .pdf-table tr:not(:first-child) td {
        padding: 5px 10px;
        color: #999;
        border-bottom: 1px solid #0a0a0a;
        white-space: nowrap;
    }
    /* Alternate rows thoda alag background */
    .pdf-table tr:nth-child(even) td { background: #060606; }

    /* ---- AI SUMMARY (card ke neeche italic text) ---- */
    .ai-summary {
        margin-top: 14px;
        padding: 10px 14px;
        border-left: 2px solid #222;
        font-size: 0.76em;
        color: #555;
        line-height: 1.8;
        font-style: italic;
    }

    /* ---- CARD FOOTER (bookmark + read more) ---- */
    .card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }

    /* ---- SAVED REPORTS PANEL (right side popup) ---- */
    #bookmark-panel {
        position: fixed;
        top: 90px; right: 20px;
        width: 265px; max-height: 400px;
        background: #0a0a0a;
        border: 1px solid #1a1a1a;
        padding: 14px;
        overflow-y: auto;
        display: none;
        z-index: 999;
        border-radius: 2px;
    }
    #bookmark-panel h3 {
        color: #ff6600;
        letter-spacing: 3px;
        font-size: 0.70em;
        border-bottom: 1px solid #1a1a1a;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }
    #bookmark-list li {
        font-size: 0.74em;
        color: #888;
        padding: 7px 0;
        cursor: pointer;
        border: none;
        border-bottom: 1px solid #0f0f0f;
        margin-bottom: 0;
    }
    #bookmark-list li:hover { color: #fff; }
"""


# ================================================================
#  STEP 11: JAVASCRIPT (INTERACTIVE FEATURES)
#
#  Yeh sab features handle karta hai:
#  - Bookmark (SAVED) button — report save/unsave
#  - SAVED panel — saved reports ki list
#  - READ MORE / READ LESS — extra bullet points dikhana
#
#  Kuch mat badlo yahan — yeh sab automatically kaam karta hai
# ================================================================

BOOKMARK_JS = """
    // Report bookmark karo / hatao
    function toggleBookmark(btn, text) {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const i = bm.indexOf(text);
        if (i === -1) { bm.push(text); btn.style.color='#ff6600'; }
        else { bm.splice(i,1); btn.style.color='#333'; }
        localStorage.setItem('bookmarks', JSON.stringify(bm));
        showBookmarks();
    }

    // SAVED panel mein list update karo
    function showBookmarks() {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.getElementById('bookmark-list').innerHTML = bm.length === 0
            ? '<li style="color:#333;cursor:default;">No saved reports</li>'
            : bm.map((b,i)=>`<li onclick="scrollToReport('${b}')">${b}
                <span onclick="event.stopPropagation();removeBookmark(${i})"
                style="float:right;color:#333;">[X]</span></li>`).join('');
        document.getElementById('bookmark-toggle').innerHTML =
            bm.length > 0 ? 'SAVED ['+bm.length+']' : 'SAVED';
    }

    // Report pe scroll karo
    function scrollToReport(t) {
        document.querySelectorAll('.report-card').forEach(card=>{
            const h = card.querySelector('h2');
            if(h && h.innerText.toLowerCase().includes(t.toLowerCase().slice(0,20))) {
                card.scrollIntoView({behavior:'smooth',block:'start'});
                togglePanel();
            }
        });
    }

    // SAVED panel open/close karo
    function togglePanel() {
        const p = document.getElementById('bookmark-panel');
        p.style.display = p.style.display==='none' ? 'block' : 'none';
    }

    // Bookmark hatao
    function removeBookmark(i) {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        bm.splice(i,1);
        localStorage.setItem('bookmarks', JSON.stringify(bm));
        showBookmarks(); markSaved();
    }

    // Saved buttons ka color set karo (orange = saved)
    function markSaved() {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.querySelectorAll('.bookmark-btn').forEach(btn=>{
            btn.style.color = bm.includes(btn.getAttribute('data-text')) ? '#ff6600' : '#333';
        });
    }

    // READ MORE / READ LESS toggle
    function toggleMore(i, btn) {
        const s = document.getElementById('more-'+i);
        if(s.style.display==='none') {
            s.style.display='block';
            btn.innerHTML='READ LESS &#9650;';
        } else {
            s.style.display='none';
            btn.innerHTML='READ MORE &#9660;';
        }
    }

    // Page load hone pe saved buttons mark karo
    window.onload = function() { showBookmarks(); markSaved(); };
"""


# ================================================================
#  STEP 12: TABLE HTML BUILDER
#
#  Table data ko HTML mein convert karta hai
#  Upar ek italic description hoti hai (Gemini se)
#  Phir table dikhti hai
# ================================================================

def build_table_html(table, sector):
    label = ai_table_description(table, sector)
    rows  = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
        for row in table
    )
    return f'<div class="table-wrap"><div class="table-label">{label}</div><table class="pdf-table">{rows}</table></div>'


# ================================================================
#  STEP 13: WEBSITE HTML BUILDER
#
#  Har report ka card banata hai aur poori website assemble karta hai
#
#  Card layout:
#  ┌─────────────────────────────────────────┐
#  │ TITLE (Gemini ne likha)                  │
#  │ Date: 19 March 2026        [ENERGY]      │
#  │ • Bullet point 1                         │
#  │ • Bullet point 2                         │
#  │ [Table — compact, clean]                 │
#  │ [READ MORE ▼]  (2 aur bullets hain)      │
#  │ Italic summary — report kya bata rahi hai│
#  │ [🔖]                      [READ MORE ▼] │
#  └─────────────────────────────────────────┘
# ================================================================

def build_website(reports, ticker_items):
    today       = datetime.today().strftime('%d %B %Y')
    ticker_html = "".join(f'<span>{t}</span>' for t in ticker_items)
    cards       = ""

    for i, r in enumerate(reports):
        title      = r.get('title', 'Untitled Report')
        sector     = r.get('sector', 'RESEARCH')
        bullets    = r.get('points', [])
        summary    = r.get('summary', '')
        tables     = r.get('tables', [])
        safe_title = title.replace("'","").replace('"','')

        # Pehle 2 bullets always dikhte hain
        vis_html = "".join(f"<li>{p}</li>" for p in bullets[:2])
        # Baaki bullets READ MORE ke peeche chhupe hain
        hid_html = "".join(f"<li>{p}</li>" for p in bullets[2:])

        hidden_sec   = f'<ul class="bullets" id="more-{i}" style="display:none;">{hid_html}</ul>' if bullets[2:] else ""
        tables_html  = "".join(build_table_html(t, sector) for t in tables)
        summary_html = f'<div class="ai-summary">{summary}</div>' if summary else ""
        read_more    = f'<button onclick="toggleMore({i},this)" style="background:none;border:none;cursor:pointer;color:#555;font-family:inherit;font-size:0.74em;letter-spacing:2px;">READ MORE &#9660;</button>' if bullets[2:] else ""

        cards += f"""
    <div class="report-card">
        <h2>{title}</h2>
        <div class="title-meta">
            <span class="date">{today}</span>
            <span class="sector-tag">{sector}</span>
        </div>
        <ul class="bullets">{vis_html}</ul>
        {tables_html}
        {hidden_sec}
        {summary_html}
        <div class="card-footer">
            <button class="bookmark-btn" data-text="{safe_title}"
                onclick="toggleBookmark(this,'{safe_title}')"
                style="background:none;border:none;cursor:pointer;color:#333;padding:0;">
                <svg width="12" height="16" viewBox="0 0 14 18" fill="currentColor">
                    <path d="M0 0h14v18l-7-4.5L0 18z"/>
                </svg>
            </button>
            {read_more}
        </div>
    </div>"""

    # Poori website HTML assemble karo
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{WEBSITE_TITLE}</title>
    <style>{WEBSITE_CSS}</style>
</head>
<body>
    <div id="site-header">
        <div id="site-logo">{WEBSITE_TITLE}</div>
        <button id="bookmark-toggle" onclick="togglePanel()">SAVED</button>
    </div>
    <div id="ticker-bar">
        <div id="ticker-content">{ticker_html}{ticker_html}</div>
    </div>
    <div id="main-content">{cards}</div>
    <div id="bookmark-panel">
        <h3>SAVED REPORTS</h3>
        <ul id="bookmark-list"></ul>
    </div>
    <script>{BOOKMARK_JS}</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html ready!")


# ================================================================
#  STEP 14: MAIN PROCESS
#
#  Yeh code sab kuch chalata hai:
#  1. pdfs/ folder scan karo
#  2. Naye PDFs dhundho (jo processed.json mein nahi hain)
#  3. Har nayi PDF ko process karo (title, bullets, summary, tables)
#  4. processed.json mein save karo
#  5. Live ticker data fetch karo
#  6. index.html update karo
#
#  NOTE: Agar koi PDF pehle se process ho chuki hai toh dobara nahi hogi
#  Sab reprocess karna ho toh: del processed.json
# ================================================================

pdf_folder     = "pdfs"           # PDFs yahan rakho
processed_file = "processed.json" # Already processed PDFs ki list

# Pehle se processed data load karo (ya empty dict banao)
processed = json.load(open(processed_file)) if os.path.exists(processed_file) else {}
new_found  = False

# Har PDF check karo
for filename in os.listdir(pdf_folder):
    if not filename.endswith(".pdf") or filename in processed:
        continue  # PDF nahi hai ya pehle se process ho chuki hai

    print(f"\nProcessing: {filename}")
    filepath = os.path.join(pdf_folder, filename)
    text     = pdf_text(filepath)
    sector   = detect_sector(text, filename)
    print(f"  Sector: {sector}")

    # Gemini se sab kuch banwao
    print(f"  Generating AI title...")
    title = ai_title(text, filename)
    print(f"  Title: {title[:70]}")

    print(f"  Generating AI bullets...")
    bullets = ai_bullets(text, sector)

    print(f"  Generating AI summary...")
    summary = ai_summary(text, sector, filename)

    print(f"  Extracting tables...")
    tables = tables_nikalo(filepath)
    print(f"  Tables found: {len(tables)}")

    # Is PDF ka data save karo
    processed[filename] = {
        'title':   title,
        'sector':  sector,
        'points':  bullets,
        'summary': summary,
        'tables':  tables,
    }
    new_found = True

# Processed data save karo
if new_found:
    with open(processed_file, "w") as f:
        json.dump(processed, f, indent=2)
    print("\nAll PDFs processed!")
else:
    print("No new PDFs found.")

# Live ticker data fetch karo
ticker_items = fetch_ticker()

# Website banao — newest reports pehle
build_website(list(reversed(list(processed.values()))), ticker_items)
print("Done! Open index.html to see the website.")