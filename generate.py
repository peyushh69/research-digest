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
#  - .env           ← API keys yahan honi chahiye
#  - processed.json ← automatically banta hai
#
#  UPDATES in this version:
#  1. Dual API key fallback — Key 1 → Key 2 → Groq (3rd fallback)
#  2. PDF delete fix — deleted PDFs website se automatically hatengi
#  3. Naye PDFs top mein — latest PDF sabse upar dikhegi
#  4. Smart caching — processed PDF dobara AI se process nahi hogi
#  5. Quantis View — har report mein AI investor opinion button
#  6. Table description caching — ek baar bani toh dobara AI call nahi
# ================================================================


# ================================================================
#  LIBRARIES — yeh sab install honi chahiye
#  Install: pip install pymupdf pdfplumber yfinance google-genai python-dotenv groq
# ================================================================

import fitz          # PyMuPDF — PDF se text nikalne ke liye
import pdfplumber    # PDF se tables nikalne ke liye
import os            # File system ke liye
import json          # Data save/load ke liye
import yfinance as yf               # Live market data ke liye
from google import genai            # Gemini AI ke liye
from groq import Groq                # Groq AI — 3rd fallback ke liye
from datetime import datetime       # Aaj ki date ke liye
from dotenv import load_dotenv      # .env file se API key load karne ke liye


# ================================================================
#  STEP 1: API KEY SETUP
#
#  .env file mein yeh hona chahiye:
#  GEMINI_API_KEY=AIzaSy...pehli_key
#  GEMINI_API_KEY_2=AIzaSy...dusri_key
#  GROQ_API_KEY=gsk_...groq_key
#
#  KABHI BHI yahan seedha key mat likho!
# ================================================================

load_dotenv()

# Purani GOOGLE_API_KEY conflict remove karo
os.environ.pop("GOOGLE_API_KEY", None)

GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")    # Pehli key
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")  # Backup key
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")      # 3rd fallback
WEBSITE_TITLE    = "Quantis"


# ================================================================
#  STEP 2: GEMINI AI HELPER
#
#  UPDATE 1: Dual API key fallback
#  - Pehle Key 1 try hogi
#  - Agar 429 quota error aaye toh automatically Key 2 use hogi
#  - Dono fail hon toh None return hoga (fallback text use hoga)
# ================================================================

def gemini(prompt):
    # STEP 1: Gemini Key 1 try karo
    # STEP 2: Agar 429 error aaye toh Gemini Key 2 try karo
    # STEP 3: Agar dono fail ho toh Groq try karo (3rd fallback)

    # Pehle dono Gemini keys try karo
    for key_name, key in [("Key 1", GEMINI_API_KEY), ("Key 2", GEMINI_API_KEY_2)]:
        if not key:
            continue
        try:
            client   = genai.Client(api_key=key)
            response = client.models.generate_content(
                model    = "gemini-2.0-flash",
                contents = prompt
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                print(f"  [Gemini {key_name} quota khatam — next try...]")
                continue  # Agla key try karo
            print(f"  [Gemini {key_name} error] {e}")
            return None

    # Gemini dono fail — Groq try karo
    if GROQ_API_KEY:
        try:
            print(f"  [Gemini quota khatam — Groq try kar raha hun...]")
            client   = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model    = "llama-3.3-70b-versatile",
                messages = [{"role": "user", "content": prompt}],
                max_tokens = 500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  [Groq error] {e}")
            return None

    print("  [Sab keys fail ho gayi]")
    return None


# ================================================================
#  STEP 3: PDF SE TEXT NIKALO
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
#  Gemini ek clean Bloomberg-style headline banata hai
#  Fallback: filename se title banta hai
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

    if result and len(result) > 10:
        return result[:130]

    name = filename.replace('.pdf','').replace('_',' ').replace('+',' ').replace('-',' ')
    return name.title()[:130]


# ================================================================
#  STEP 5: SECTOR AUTO-DETECT
#
#  Filename + content se sector detect hota hai
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
    check = (filename + " " + text[:2000]).lower()
    for sector, keywords in SECTOR_MAP.items():
        for kw in keywords:
            if kw in check:
                return sector
    return 'RESEARCH'


# ================================================================
#  STEP 6: AI BULLET POINTS GENERATOR
#
#  4 crisp economic facts — koi stock tips nahi
#  Double protection: prompt + post-processing filter
# ================================================================

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
        lines = [l for l in lines if not any(w in l.lower() for w in STOCK_TIP_WORDS)]
        return lines[:4] if lines else ["Key economic data available in the original report."]
    return ["Key economic data available in the original report."]


# ================================================================
#  STEP 7: AI SUMMARY GENERATOR
#
#  2 sentence plain language summary — report kya kehna chahti hai
#  Max 400 characters, koi stock tips nahi
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


def ai_commentary(text, sector, filename):
    """READ MORE ke andar — poori report ki 300 char summary, plain language mein"""
    result = gemini(f"""Write a plain-language summary of this research report in maximum 300 characters.

Rules:
- Someone reads it once and understands the full report
- Include key numbers/data points
- No BUY/SELL/HOLD tips
- No broker names
- Simple, clear English
- Strictly under 300 characters

Sector: {sector}
Report: {text[:3000]}

Summary (max 300 chars):""")
    if result:
        # Clean prefix agar AI ne likh diya
        clean = result.strip().lstrip('-*+.')
        return [clean[:300]]
    return []


# ================================================================
#  STEP 7B: QUANTIS VIEW GENERATOR
#
#  Har report ke liye automatic trader-style view
#  User ko kuch type nahi karna — AI khud banata hai
#  processed.json mein cache hota hai — dobara call nahi hogi
# ================================================================

def ai_quantis_view(text, sector, filename):
    result = gemini(f"""Analyze the following data and write a professional "Quantis View" in 1–2 lines.

Focus on:
• What the data signals
• Impact on markets or interest rates
• Affected sectors or stocks

Keep it sharp, trader-focused, and actionable. Avoid generic explanation. Use market language like "pressure", "support", "upside", "downside", "rate cuts", etc.

Sector: {sector}
Report: {text[:2500]}

Quantis View:""")
    if result:
        # "Quantis View:" prefix remove karo agar AI ne likh diya
        result = result.strip()
        for prefix in ['Quantis View:', 'quantis view:', 'QUANTIS VIEW:', 'Quantis View -']:
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix):].strip()
        lines = [l.strip().lstrip('-*+.') for l in result.split('\n') if l.strip()]
        lines = [l for l in lines if len(l) > 15]
        return ' '.join(lines[:2])[:300]
    return None


# ================================================================
#  STEP 8: TABLE EXTRACTION + CLEANING
#
#  pdfplumber se tables nikalte hain
#  Pure recommendation tables skip hoti hain
#  BUY/SELL columns remove hote hain
#  Max 2 tables per PDF
# ================================================================

RATING_WORDS   = {'buy','sell','hold','accumulate','overweight','underweight',
                  'outperform','underperform','neutral','reduce','add'}
RATING_HEADERS = {'reco','rating','recommendation','call','stance','view','recom','tp'}

def is_recommendation_table(table):
    if not table or not table[0]:
        return False
    headers   = [str(c).lower().strip() for c in table[0] if c]
    rec_count = sum(1 for h in headers if h in RATING_HEADERS or 'target' in h)
    return rec_count >= 2

def remove_rating_columns(table):
    if not table or not table[0]:
        return table
    remove = set()
    for ci, cell in enumerate(table[0]):
        if str(cell).lower().strip() in RATING_HEADERS:
            remove.add(ci)
    if len(table) > 2:
        for ci in range(len(table[0])):
            vals = [str(table[ri][ci]).lower().strip()
                    for ri in range(1, min(len(table), 8))
                    if ci < len(table[ri])]
            if vals and sum(1 for v in vals if v in RATING_WORDS) / len(vals) > 0.4:
                remove.add(ci)
    if not remove:
        return table
    return [[c for ci, c in enumerate(row) if ci not in remove] for row in table]

def tables_nikalo(filepath):
    extracted = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    if not table:
                        continue
                    clean = [[str(c).strip() if c else "" for c in row]
                             for row in table if any(c for c in row)]
                    if len(clean) < 2 or len(clean[0]) < 2:
                        continue
                    if is_recommendation_table(clean):
                        print(f"  Skipped recommendation table")
                        continue
                    clean = remove_rating_columns(clean)
                    extracted.append(clean)
                    if len(extracted) >= 2:
                        return extracted
    except Exception as e:
        print(f"  [Table error] {e}")
    return extracted

def ai_table_description(table, sector):
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
#  yfinance se live Nifty, Sensex, Gold, Crude etc.
#  White background, black text, 90s slow scroll
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
#  Black background, orange accent, IBM Plex Mono font
#  UPDATE 5: Quantis View button style added (same as READ MORE)
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

    /* ---- HEADER ---- */
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

    /* ---- HAMBURGER DRAWER ---- */
    #nav-drawer {
        position: fixed;
        top: 0; right: -260px;
        width: 240px;
        height: 100vh;
        background: #050505;
        border-left: 1px solid #1a1a1a;
        z-index: 999;
        padding: 20px 0;
        transition: right 0.25s ease;
    }
    #nav-drawer.open { right: 0; }
    #nav-drawer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 20px 16px;
        border-bottom: 1px solid #1a1a1a;
        margin-bottom: 10px;
    }
    .drawer-link {
        display: block;
        padding: 14px 20px;
        color: #555;
        text-decoration: none;
        font-size: 0.80em;
        font-weight: 700;
        letter-spacing: 3px;
        border-bottom: 1px solid #0f0f0f;
        transition: color 0.2s;
    }
    .drawer-link:hover { color: #fff; background: #0a0a0a; }
    .drawer-link.active { color: #ff6600; }
    #nav-overlay {
        display: none;
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background: rgba(0,0,0,0.6);
        z-index: 998;
    }
    #nav-overlay.open { display: block; }

    /* SAVED button */
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

    /* ---- TICKER BAR ---- */
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
        animation: scroll-ticker 90s linear infinite;
        padding-left: 100%;
    }
    #ticker-content span { margin-right: 60px; color: #000; }
    @keyframes scroll-ticker {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }

    /* ---- MAIN CONTENT ---- */
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

    /* ---- DATE + SECTOR TAG ---- */
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
    .pdf-table tr:first-child td {
        background: #0d0600;
        color: #ff6600;
        font-weight: 700;
        padding: 6px 10px;
        border-bottom: 1px solid #ff6600;
        white-space: nowrap;
    }
    .pdf-table tr:not(:first-child) td {
        padding: 5px 10px;
        color: #999;
        border-bottom: 1px solid #0a0a0a;
        white-space: nowrap;
    }
    .pdf-table tr:nth-child(even) td { background: #060606; }
    /* Table color coding — positive=green, negative=red, neutral=yellow */
    .pdf-table td.num-pos { color: #4caf50 !important; }
    .pdf-table td.num-neg { color: #f44336 !important; }
    .pdf-table td.num-neu { color: #b8a040 !important; }

    /* ---- AI SUMMARY ---- */
    .ai-summary {
        margin-top: 14px;
        padding: 10px 14px;
        border-left: 2px solid #222;
        font-size: 0.76em;
        color: #555;
        line-height: 1.8;
        font-style: italic;
    }

    /* ---- CARD FOOTER ---- */
    .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 14px;
    }

    /* ---- QUANTIS VIEW — title ke bagal mein chhota tag ---- */
    .qv-title-tag {
        font-size: 0.55em;
        color: #4a3a2a;
        letter-spacing: 1.5px;
        font-weight: 400;
        margin-left: 10px;
        vertical-align: middle;
        cursor: pointer;
        border-bottom: 1px dotted #4a3a2a;
    }
    .qv-title-tag:hover { color: #6b5a45; }

    /* Input box jo QUANTIS VIEW click karne pe open hota hai */
    .quantis-view-box {
        display: none;
        margin-top: 12px;
        background: #0a0a08;
        border: 1px solid #1a1a12;
        border-left: 2px solid #4a3a2a;
        padding: 10px 14px;
    }
    .quantis-view-box textarea {
        width: 100%;
        background: transparent;
        border: none;
        border-bottom: 1px solid #1a1a1a;
        color: #888;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.74em;
        padding: 4px 0 8px;
        resize: none;
        height: 40px;
        outline: none;
        letter-spacing: 0.5px;
    }
    .quantis-view-box textarea::placeholder { color: #2a2a2a; }
    .quantis-view-box textarea:focus { border-bottom-color: #4a3a2a; }

    /* AI response — browny/muted */
    .quantis-view-result {
        margin-top: 8px;
        font-size: 0.72em;
        color: #6b5a45;
        font-style: italic;
        line-height: 1.7;
        letter-spacing: 0.3px;
        min-height: 0;
    }

    /* ---- AUTO QUANTIS VIEW (har card mein auto trader view) ---- */
    .auto-quantis-view {
        margin-top: 12px;
        padding: 8px 12px;
        background: #050503;
        border-left: 2px solid #4a3a2a;
        font-size: 0.74em;
        color: #6b5a45;
        font-style: italic;
        line-height: 1.7;
        letter-spacing: 0.3px;
    }
    .aqv-label {
        font-style: normal;
        font-weight: 700;
        font-size: 0.80em;
        color: #4a3a2a;
        letter-spacing: 2px;
        margin-right: 8px;
    }

    /* ---- REPORT SUMMARY (READ MORE ke andar) ---- */
    .commentary-label {
        font-size: 0.60em;
        color: #ff6600;
        letter-spacing: 2px;
        margin: 14px 0 8px;
        font-weight: 700;
    }
    .commentary-summary {
        font-size: 0.82em;
        color: #777;
        line-height: 1.8;
        font-style: italic;
        border-left: 2px solid #1a1a1a;
        padding-left: 12px;
        margin-bottom: 10px;
    }

    /* ---- SAVED PANEL ---- */
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
#  STEP 11: JAVASCRIPT
#
#  - Bookmark (SAVED) toggle
#  - READ MORE / READ LESS
#  - UPDATE 5: Quantis View — user type kare, Gemini investor opinion de
# ================================================================

BOOKMARK_JS = """
    // Bookmark toggle
    function toggleBookmark(btn, text) {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const i = bm.indexOf(text);
        if (i === -1) { bm.push(text); btn.style.color='#ff6600'; }
        else { bm.splice(i,1); btn.style.color='#333'; }
        localStorage.setItem('bookmarks', JSON.stringify(bm));
        showBookmarks();
    }

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

    function scrollToReport(t) {
        document.querySelectorAll('.report-card').forEach(card=>{
            const h = card.querySelector('h2');
            if(h && h.innerText.toLowerCase().includes(t.toLowerCase().slice(0,20))) {
                card.scrollIntoView({behavior:'smooth',block:'start'});
                togglePanel();
            }
        });
    }

    function togglePanel() {
        const p = document.getElementById('bookmark-panel');
        p.style.display = p.style.display==='none' ? 'block' : 'none';
    }

    function removeBookmark(i) {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        bm.splice(i,1);
        localStorage.setItem('bookmarks', JSON.stringify(bm));
        showBookmarks(); markSaved();
    }

    function markSaved() {
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.querySelectorAll('.bookmark-btn').forEach(btn=>{
            btn.style.color = bm.includes(btn.getAttribute('data-text')) ? '#ff6600' : '#333';
        });
    }

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

    // ---- UPDATE 5: QUANTIS VIEW ----
    // User ka question + report context Gemini ko bheja jaata hai
    // Response 150 characters mein, investor perspective se

    function toggleQuantisView(i) {
        const box = document.getElementById('qv-box-'+i);
        box.style.display = box.style.display === 'none' ? 'block' : 'none';
        if(box.style.display === 'block') {
            box.querySelector('textarea').focus();
        }
    }

    async function askQuantisView(i) {
        const textarea = document.getElementById('qv-input-'+i);
        const result   = document.getElementById('qv-result-'+i);
        const question = textarea.value.trim();
        const context  = document.getElementById('qv-context-'+i).value;

        if(!question) return;

        result.innerText = 'thinking...';

        try {
            const resp = await fetch('https://api.anthropic.com/v1/messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'claude-sonnet-4-20250514',
                    max_tokens: 100,
                    messages: [{
                        role: 'user',
                        content: `You are Quantis — a sharp Indian trader/analyst. Answer like a seasoned trader thinks.

Style rules (VERY IMPORTANT):
- Use arrow format: "X upar gaya → Y hoga → Z sector pe impact"
- Short, punchy, cause-effect chain
- Max 2 sentences, max 150 characters total
- No formal language. Think like a trader on a trading desk.
- Reply in SAME language as the question (Hindi/English/Hinglish)
- Example style: "WPI upar → cost pressure → RBI cut delay → Banks/Realty pe sell pressure near term"

Report context: \${context}
User question: \${question}

Trader-style answer (max 150 chars):`
                    }]
                })
            });
            const data = await resp.json();
            const text = data.content && data.content[0] ? data.content[0].text : 'Could not get response.';
            result.innerText = text.slice(0, 150);
        } catch(e) {
            result.innerText = 'Error. Please try again.';
        }
    }

    // Enter press karne pe submit ho
    function qvKeydown(e, i) {
        if(e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askQuantisView(i);
        }
    }

    window.onload = function() { showBookmarks(); markSaved(); };

    // Hamburger menu toggle
    function toggleMenu() {
        document.getElementById('nav-drawer').classList.toggle('open');
        document.getElementById('nav-overlay').classList.toggle('open');
    }
"""


# ================================================================
#  STEP 12: TABLE HTML BUILDER
# ================================================================

def color_cell(val):
    """Number detect karo aur color class lagao — red/green/yellow"""
    try:
        # Brackets wale negative numbers jaise (3.21)
        v = str(val).strip().replace(',','').replace('%','').replace('$','')
        if v.startswith('(') and v.endswith(')'):
            return 'num-neg'
        num = float(v)
        if num > 0:   return 'num-pos'  # Green
        if num < 0:   return 'num-neg'  # Red
        return 'num-neu'                 # Yellow — zero
    except:
        return ''  # Text hai — koi color nahi

def build_table_html(table, label, sector):
    # UPDATE 6: label ab processed.json se aata hai — AI call nahi hoti
    if not label:
        label = f"Key metrics — {sector} sector"

    rows = ""
    for ri, row in enumerate(table):
        cells = ""
        for ci, c in enumerate(row):
            if ri == 0:
                # Header row — orange color already CSS mein hai
                cells += f"<td>{c}</td>"
            else:
                # Data row — number check karo, color lagao
                cls = color_cell(c)
                cells += f'<td class="{cls}">{c}</td>' if cls else f"<td>{c}</td>"
        rows += f"<tr>{cells}</tr>"

    return f'<div class="table-wrap"><div class="table-label">{label}</div><table class="pdf-table">{rows}</table></div>'


# ================================================================
#  STEP 13: WEBSITE HTML BUILDER
#
#  UPDATE 3: Naye PDFs top mein (main process mein sort hota hai)
#  UPDATE 5: Har card mein Quantis View button + input box
#
#  Card layout:
#  ┌─────────────────────────────────────────┐
#  │ TITLE                                    │
#  │ Date left          SECTOR TAG right      │
#  │ • Bullet 1                               │
#  │ • Bullet 2                               │
#  │ [Table]                                  │
#  │ [READ MORE ▼]                            │
#  │ Italic AI summary                        │
#  │ [🔖 Bookmark]  [QUANTIS VIEW] [READ MORE]│
#  │ [Input box — type karo, AI jawab dega]   │
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
        commentary = r.get('commentary', [])
        tables     = r.get('tables', [])
        safe_title = title.replace("'","").replace('"','')

        quantis_view = r.get('quantis_view', '')

        # Pehle 2 bullets dikhte hain
        vis_html = "".join(f"<li>{p}</li>" for p in bullets[:2])

        # READ MORE mein: baaki bullets + commentary section
        hid_bullets = "".join(f"<li>{p}</li>" for p in bullets[2:])
        hid_com = ""
        if commentary:
            com_text = commentary[0] if commentary else ""
            hid_com = f'<div class="commentary-label">REPORT SUMMARY</div><div class="commentary-summary">{com_text}</div>'

        has_more   = bool(bullets[2:] or commentary)
        hid_inner  = (f'<ul class="bullets">{hid_bullets}</ul>' if hid_bullets else "") + hid_com
        hidden_sec = f'<div id="more-{i}" style="display:none;">{hid_inner}</div>' if has_more else ""

        table_descs  = r.get('table_descs', [''] * len(tables))
        tables_html  = "".join(build_table_html(t, table_descs[j] if j < len(table_descs) else '', sector) for j, t in enumerate(tables))
        read_more    = f'<button onclick="toggleMore({i},this)" style="background:none;border:none;cursor:pointer;color:#555;font-family:inherit;font-size:0.74em;letter-spacing:2px;">READ MORE &#9660;</button>' if has_more else ""

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
        {f'<div class="auto-quantis-view"><span class="aqv-label">QUANTIS VIEW</span> {quantis_view}</div>' if quantis_view else ""}
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
        <div style="display:flex;align-items:center;gap:14px;">
            <button id="bookmark-toggle" onclick="togglePanel()">SAVED</button>
            <button id="hamburger" onclick="toggleMenu()" style="background:none;border:none;cursor:pointer;color:#888;font-size:1.4em;padding:0;line-height:1;">&#9776;</button>
        </div>
    </div>
    <!-- Hamburger Drawer -->
    <div id="nav-drawer">
        <div id="nav-drawer-header">
            <span style="color:#ff6600;font-size:0.75em;letter-spacing:3px;font-weight:700;">MENU</span>
            <button onclick="toggleMenu()" style="background:none;border:none;color:#444;cursor:pointer;font-size:1.2em;">&#10005;</button>
        </div>
        <nav id="drawer-nav">
            <a href="index.html" class="drawer-link">HOME</a>
            <a href="research.html" class="drawer-link active">RESEARCH</a>
            <a href="market.html" class="drawer-link">MARKET</a>
            <a href="economy.html" class="drawer-link">ECONOMY</a>
            <a href="#" class="drawer-link" onclick="togglePanel();toggleMenu();">SAVED</a>
        </nav>
    </div>
    <div id="nav-overlay" onclick="toggleMenu()"></div>
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

    with open("research.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("research.html ready!")


# ================================================================
#  STEP 14: MAIN PROCESS
#
#  UPDATE 2: PDF delete fix
#  - processed.json mein se deleted PDFs ki entries remove hoti hain
#  - Woh reports website pe nahi dikhti
#
#  UPDATE 3: Naye PDFs top mein
#  - processed dict mein 'added_at' timestamp save hoti hai
#  - Website build karte waqt newest pehle sort hota hai
#
#  UPDATE 4: Smart caching (already tha, confirm + comment)
#  - Agar PDF processed.json mein hai toh Gemini call NAHI hogi
#  - Sirf naye PDFs process hote hain — tokens bachte hain
# ================================================================

pdf_folder     = "pdfs"
processed_file = "processed.json"

# Pehle se processed data load karo
processed = json.load(open(processed_file)) if os.path.exists(processed_file) else {}

# ---- UPDATE 2: PDF DELETE FIX ----
# pdfs/ folder mein jo PDFs hain unki list banao
current_pdfs = set(f for f in os.listdir(pdf_folder) if f.endswith(".pdf"))
# processed.json mein jo entries hain unme se deleted PDFs hatao
deleted = [f for f in list(processed.keys()) if f not in current_pdfs]
for f in deleted:
    print(f"Removing deleted PDF from website: {f}")
    del processed[f]
if deleted:
    with open(processed_file, "w") as f:
        json.dump(processed, f, indent=2)

# Naye PDFs process karo
new_found = False
for filename in os.listdir(pdf_folder):
    if not filename.endswith(".pdf"):
        continue

    # ---- UPDATE 4: SMART CACHING ----
    # Pehle se process ho chuki PDF? Skip karo — Gemini call mat karo
    if filename in processed:
        continue

    print(f"\nProcessing: {filename}")
    filepath = os.path.join(pdf_folder, filename)
    text     = pdf_text(filepath)
    sector   = detect_sector(text, filename)
    print(f"  Sector: {sector}")

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

    # ---- UPDATE 6: TABLE DESCRIPTIONS CACHE ----
    # Gemini se table descriptions ek baar banao aur save karo
    # Dobara generate.py chalane pe AI call nahi hogi
    print(f"  Generating table descriptions...")
    table_descs = [ai_table_description(t, sector) for t in tables]

    print(f"  Generating commentary...")
    commentary = ai_commentary(text, sector, filename)

    print(f"  Generating Quantis View...")
    quantis_view = ai_quantis_view(text, sector, filename)

    # ---- UPDATE 3: TIMESTAMP SAVE KARO (newest first ke liye) ----
    processed[filename] = {
        'title':        title,
        'sector':       sector,
        'points':       bullets,
        'summary':      summary,
        'commentary':   commentary,    # READ MORE mein dikhegi
        'quantis_view': quantis_view,  # Auto trader view — cached
        'tables':       tables,
        'table_descs':  table_descs,
        'added_at':     datetime.now().isoformat(),
    }
    new_found = True

# Save karo
if new_found or deleted:
    with open(processed_file, "w") as f:
        json.dump(processed, f, indent=2)
    print("\nAll PDFs processed!")
else:
    print("No new PDFs found.")

# Live ticker
ticker_items = fetch_ticker()

# ---- UPDATE 3: NEWEST FIRST SORT ----
# added_at timestamp ke hisaab se sort karo — naye PDF upar
sorted_reports = sorted(
    processed.values(),
    key=lambda r: r.get('added_at', ''),
    reverse=True  # Newest first
)

build_website(sorted_reports, ticker_items)
print("Done! Open index.html to see the website.")