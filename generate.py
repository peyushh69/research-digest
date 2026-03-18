# ============================================================
#  QUANTIS - RESEARCH DIGEST GENERATOR
#  This script reads PDFs from the pdfs/ folder and builds index.html
#  How to run: python generate.py
# ============================================================

# These are the libraries we need.
# fitz = reads PDF files
# os = reads folders and file paths
# json = saves which PDFs have already been processed
# nltk + sumy = extracts key points from text
# datetime = gets today's date
import fitz
import os
import json
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from datetime import datetime

# These language tools are needed for summarization to work.
# quiet=True means they won't print anything when downloading.
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)


# ============================================================
#  SECTION 1: PDF TEXT EXTRACTOR
#  DO NOT TOUCH — this is the core PDF reading logic
#  It opens a PDF, reads every page, and returns all text
# ============================================================

def pdf_se_text_nikalo(filepath):
    doc = fitz.open(filepath)  # Open the PDF file
    poora_text = ""
    for page in doc:           # Loop through every page
        poora_text += page.get_text()  # Extract text from each page
    doc.close()
    return poora_text          # Return all the collected text


# ============================================================
#  SECTION 2: FILTER WORDS LIST
#  If any unwanted word appears in a bullet point, that line is skipped.
#  ADD new words here if you see junk text appearing in your output.
#  Example: if "proprietary" keeps appearing, add 'proprietary' to this list.
# ============================================================

FILTER_WORDS = [
    'disclaimer',               # Legal disclaimer text
    'views expressed',          # Author opinion disclaimers
    'do not necessarily',       # Standard legal phrase
    'reflect the views',        # Standard legal phrase
    'personal views',           # Author note
    'author',                   # Author name lines
    'nothing contained',        # Legal boilerplate
    'shall constitute',         # Legal boilerplate
    'solicitation',             # Legal boilerplate
    'offer to sell',            # Legal boilerplate
    'offer to purchase',        # Legal boilerplate
    'securities',               # Legal boilerplate
    'invitation or solicitation',  # Legal boilerplate
    'any entity',               # Legal boilerplate
    'accuracy',                 # Legal accuracy disclaimer
    'completeness',             # Legal completeness disclaimer
    'reliability',              # Legal reliability disclaimer
    'representation'            # Legal representation disclaimer
]


# ============================================================
#  SECTION 3: KEY POINTS EXTRACTOR
#  This function cleans the PDF text and picks the most important sentences.
#
#  TO CUSTOMIZE:
#  kitne_points = how many bullet points per report (default: 5)
#  min_line_length = lines shorter than this are ignored (removes headings/names)
#  max_line_length = lines longer than this are ignored (removes run-on sentences)
# ============================================================

def key_points_nikalo(text, kitne_points=5):
    min_line_length = 60    # Lines shorter than 60 chars are skipped (e.g. "Page 1", author names)
    max_line_length = 200   # Lines longer than 200 chars are skipped (too complex to show as a point)

    clean_lines = []
    for line in text.split('\n'):
        line = line.strip()  # Remove extra spaces from start and end

        # Skip lines with email addresses
        if '@' in line:
            continue

        # Skip lines that are too short (headings, page numbers, names)
        if len(line) < min_line_length:
            continue

        # Skip lines that are too long (run-on sentences)
        if len(line) > max_line_length:
            continue

        # Skip lines containing any filter words defined in Section 2
        if any(word in line.lower() for word in FILTER_WORDS):
            continue

        clean_lines.append(line)  # If line passes all checks, keep it

    # Join all clean lines into one block of text
    clean_text = ' '.join(clean_lines)

    # Use LSA summarizer to pick the most important sentences
    parser = PlaintextParser.from_string(clean_text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, kitne_points)

    return [str(sentence) for sentence in summary]  # Return as a list of strings


# ============================================================
#  SECTION 4: WEBSITE DESIGN (CSS)
#  ONLY edit this section to change colors, fonts, or layout.
#
#  CURRENT SETTINGS:
#  - Background: Black (#000000)
#  - Main text: Orange (#ff6600) — Bloomberg Terminal style
#  - Title heading: White (#ffffff)
#  - Font: IBM Plex Mono (clean monospace, professional look)
#  - Cards: No box border, separated by a thin brown bottom line
#
#  HOW TO CHANGE COLORS:
#  Replace any color code like #ff6600 with your desired color.
#  Use Google "color picker" to find color codes.
#
#  HOW TO CHANGE FONT:
#  Replace 'IBM Plex Mono' with any Google Font name.
#  Also update the @import URL at the top of this section.
# ============================================================

WEBSITE_CSS = """
    /* Import fonts from Google Fonts — IBM Plex Mono is the main font */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');

    /* ---- GLOBAL PAGE SETTINGS ---- */
    /* Controls the overall page background, font, and text color */
    body {
        font-family: 'IBM Plex Mono', monospace;  /* Main font for all text */
        max-width: 960px;          /* Maximum page width — keeps content readable */
        margin: 40px auto;         /* Centers the content on the page */
        padding: 0 20px;           /* Left-right padding so text doesn't touch screen edge */
        background: #000000;       /* PAGE BACKGROUND COLOR — change this */
        color: #ff6600;            /* DEFAULT TEXT COLOR (orange) — change this */
    }

    /* ---- MAIN PAGE HEADING (QUANTIS title at top) ---- */
    /* This styles the big "Quantis" title at the top of the page */
    h1 {
        font-size: 2em;            /* Title size — increase for bigger title */
        font-family: 'IBM Plex Mono', monospace;
        color: #ffffff;            /* TITLE COLOR — currently white */
        border-bottom: 1px solid #ff6600;  /* Orange line under the title */
        padding-bottom: 10px;
        letter-spacing: 2px;       /* Spacing between letters */
        font-weight: 700;          /* Bold */
        text-transform: none;      /* Keeps original capitalization */
    }

    /* ---- REPORT CARD (each PDF is shown as a card) ---- */
    /* Each report is separated by a thin brown bottom border — no box */
    .report-card {
        background: #000000;       /* Card background — matches page */
        border: none;              /* No box border */
        border-bottom: 1px solid #3a1a00;  /* THIN BROWN SEPARATOR LINE — change color here */
        padding: 20px 0;           /* Top-bottom spacing inside each card */
        margin: 10px 0;            /* Space between cards */
    }

    /* ---- REPORT TITLE (name of the PDF shown in each card) ---- */
    .report-card h2 {
        font-size: 0.9em;
        color: #ffaa00;            /* REPORT TITLE COLOR — currently yellow-orange */
        text-transform: uppercase; /* Makes title ALL CAPS */
        letter-spacing: 2px;
        margin-bottom: 4px;
        font-weight: 700;
    }

    /* ---- DATE LINE (shows when the report was processed) ---- */
    .date {
        font-size: 0.75em;
        color: #884400;            /* DATE TEXT COLOR — currently dark orange */
        margin-bottom: 12px;
    }

    /* ---- BULLET POINTS LIST ---- */
    ul {
        line-height: 1.9;          /* Line spacing between bullet points */
        padding-left: 20px;
    }

    /* ---- INDIVIDUAL BULLET POINT ---- */
    li {
        margin-bottom: 6px;
        color: #ff6600;            /* BULLET TEXT COLOR — change this */
        border-bottom: 1px solid #1a0a00;  /* Very subtle dark line under each point */
        padding-bottom: 5px;
    }

    /* The bullet dot color */
    li::marker {
        color: #ffaa00;            /* BULLET DOT COLOR — change this */
    }

    /* ---- CARD FOOTER (bookmark icon + read more button) ---- */
    /* This is the bottom row of each card */
    .card-footer {
        display: flex;
        justify-content: space-between;  /* Bookmark on left, Read More on right */
        align-items: center;
        margin-top: 12px;
        padding-top: 8px;
        border-top: 1px solid #1a0a00;
    }

    /* ---- BOOKMARK TOGGLE BUTTON (top right corner of page) ---- */
    /* This is the fixed button in the top-right that opens saved reports */
    #bookmark-toggle {
        position: fixed;           /* Stays in place even when scrolling */
        top: 20px;
        right: 20px;
        background: none;
        border: 1px solid #ff6600;
        color: #ff6600;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75em;
        padding: 6px 12px;
        cursor: pointer;
        letter-spacing: 2px;
        z-index: 1000;             /* Makes sure it stays above all other elements */
    }

    /* ---- BOOKMARK DROPDOWN PANEL (opens when SAVED button is clicked) ---- */
    #bookmark-panel {
        position: fixed;           /* Stays in place when scrolling */
        top: 50px;
        right: 20px;
        width: 260px;
        max-height: 400px;         /* Panel won't grow taller than this */
        background: #0a0500;       /* Dark panel background */
        border: 1px solid #ff6600;
        padding: 16px;
        overflow-y: auto;          /* Scroll inside panel if too many bookmarks */
        display: none;             /* Hidden by default, shown when button clicked */
        z-index: 999;
    }

    /* Panel heading — "SAVED REPORTS" */
    #bookmark-panel h3 {
        color: #ffaa00;
        letter-spacing: 3px;
        font-size: 0.75em;
        border-bottom: 1px solid #ff6600;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }

    /* Each saved report item in the panel */
    #bookmark-list li {
        font-size: 0.75em;
        line-height: 1.6;
        color: #ff6600;
        border-bottom: 1px solid #1a0a00;
        padding: 6px 0;
    }
"""


# ============================================================
#  SECTION 5: WEBSITE TITLE AND HEADING
#  WEBSITE_TITLE = text shown in the browser tab
#  WEBSITE_HEADING = big title shown at top of the page
#  Change both to rename your website.
# ============================================================

WEBSITE_TITLE = "Quantis"       # Shown in browser tab
WEBSITE_HEADING = "Quantis"     # Shown at top of page


# ============================================================
#  SECTION 5B: JAVASCRIPT — BOOKMARK + READ MORE LOGIC
#  DO NOT TOUCH — this handles all interactive features:
#  1. Saving/removing bookmarks using browser's local storage
#  2. Showing/hiding the bookmark panel
#  3. Toggling the Read More / Read Less section on each card
# ============================================================

BOOKMARK_JS = """
    // Adds or removes a report from saved bookmarks
    // Uses localStorage so bookmarks survive browser restarts
    function toggleBookmark(btn, text) {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const index = bookmarks.indexOf(text);

        if (index === -1) {
            bookmarks.push(text);           // Add to bookmarks
            btn.style.color = '#cc4400';    // Turn bookmark icon dark orange
            btn.title = 'Saved!';
        } else {
            bookmarks.splice(index, 1);     // Remove from bookmarks
            btn.style.color = '#333';       // Turn bookmark icon grey
            btn.title = 'Bookmark this report';
        }
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        showBookmarks();
    }

    // Renders the bookmark list inside the panel
    // Also updates the SAVED button to show count
    function showBookmarks() {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        const panel = document.getElementById('bookmark-panel');
        const list = document.getElementById('bookmark-list');
        const btn = document.getElementById('bookmark-toggle');

        // If no bookmarks, show a placeholder message
        list.innerHTML = bookmarks.length === 0
            ? '<li style="color:#884400">No saved reports</li>'
            : bookmarks.map((b, i) => `
                <li>${b}
                    <span onclick="removeBookmark(${i})"
                          style="cursor:pointer; color:#884400; float:right;">[X]</span>
                </li>`).join('');

        // Update button label to show count of saved reports
        btn.innerHTML = bookmarks.length > 0
            ? 'SAVED [' + bookmarks.length + ']'
            : 'SAVED';
    }

    // Opens or closes the bookmark panel when SAVED button is clicked
    function togglePanel() {
        const panel = document.getElementById('bookmark-panel');
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }

    // Removes a specific bookmark by its index in the array
    function removeBookmark(index) {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        bookmarks.splice(index, 1);
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        showBookmarks();
        markSavedButtons();
    }

    // On page load, highlights bookmark icons that are already saved
    function markSavedButtons() {
        let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.querySelectorAll('.bookmark-btn').forEach(btn => {
            const text = btn.getAttribute('data-text');
            btn.style.color = bookmarks.includes(text) ? '#cc4400' : '#333';
        });
    }

    // Shows/hides the extra bullet points in a card (Read More / Read Less)
    function toggleMore(i, btn) {
        const section = document.getElementById('more-' + i);
        if (section.style.display === 'none') {
            section.style.display = 'block';
            btn.innerHTML = 'READ LESS &#9650;';   // Arrow pointing up
        } else {
            section.style.display = 'none';
            btn.innerHTML = 'READ MORE &#9660;';   // Arrow pointing down
        }
    }

    // Runs when the page first loads
    window.onload = function() {
        showBookmarks();
        markSavedButtons();
    };
"""


# ============================================================
#  SECTION 6: HTML PAGE BUILDER
#  DO NOT TOUCH — assembles all sections into the final HTML page
#
#  CARD LAYOUT (for each report):
#  [Report Title]
#  [Processed date]
#  - Point 1 (always visible)
#  - Point 2 (always visible)
#  [Hidden points, shown on READ MORE click]
#  [Bookmark icon (left)]     [READ MORE button (right)]
# ============================================================

def website_banao(reports_data):
    aaj_ki_tarikh = datetime.today().strftime('%d %B %Y')  # Example: 18 March 2026

    all_cards = ""  # Will hold all the report card HTML

    for i, report in enumerate(reports_data):
        # Split points: first 2 are always visible, rest are hidden
        visible_points = report['points'][:2]
        hidden_points = report['points'][2:]

        # Build HTML list items for visible points
        visible_html = "".join(f"            <li>{p}</li>\n" for p in visible_points)

        # Build HTML list items for hidden points
        hidden_html = "".join(f"            <li>{p}</li>\n" for p in hidden_points)

        # Only create hidden section if there are extra points to show
        hidden_section = ""
        if hidden_points:
            hidden_section = f"""
        <ul id="more-{i}" style="display:none; margin-top:0; padding-left:20px;">
{hidden_html}        </ul>"""

        # Safe version of title for use inside JavaScript (removes quotes)
        safe_title = report['title'].replace("'", "").replace('"', '')

        # Build the full card HTML for this report
        all_cards += f"""
    <div class="report-card">
        <h2>{report['title']}</h2>
        <div class="date">Processed on: {aaj_ki_tarikh}</div>

        <!-- Always visible bullet points (first 2) -->
        <ul style="padding-left:20px;">
{visible_html}        </ul>

        <!-- Hidden bullet points (shown on READ MORE) -->
        {hidden_section}

        <!-- Footer: bookmark icon on left, read more button on right -->
        <div class="card-footer">

            <!-- Bookmark ribbon icon — turns dark orange when saved -->
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

            <!-- Read More button — expands/collapses hidden points -->
            <button onclick="toggleMore({i}, this)"
                    style="background:none; border:none; cursor:pointer;
                           color:#884400; font-family:inherit; font-size:0.8em;
                           letter-spacing:2px; text-transform:uppercase;">
                READ MORE &#9660;
            </button>

        </div>
    </div>"""

    # Assemble the final HTML page using all the sections above
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{WEBSITE_TITLE}</title>
    <style>
{WEBSITE_CSS}
    </style>
</head>
<body>

    <!-- Main page title -->
    <h1>{WEBSITE_HEADING}</h1>

    <!-- Fixed button in top-right corner to open/close bookmark panel -->
    <button id="bookmark-toggle" onclick="togglePanel()">SAVED</button>

    <!-- Bookmark dropdown panel (hidden by default) -->
    <div id="bookmark-panel">
        <h3>SAVED REPORTS</h3>
        <ul id="bookmark-list"></ul>
    </div>

    <!-- All report cards go here -->
    {all_cards}

    <!-- JavaScript for bookmarks and read more -->
    <script>
{BOOKMARK_JS}
    </script>

</body>
</html>"""

    # Write the final HTML to index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html updated successfully!")


# ============================================================
#  SECTION 7: MAIN PROCESS
#  DO NOT TOUCH — this is the engine that runs everything
#
#  HOW IT WORKS:
#  1. Reads processed.json to know which PDFs are already done
#  2. Scans the pdfs/ folder for any new PDF files
#  3. Processes only new PDFs (skips already processed ones)
#  4. Saves updated list to processed.json
#  5. Always rebuilds index.html (so design changes apply instantly)
# ============================================================

pdf_folder = "pdfs"              # Folder where you drop your PDF files
processed_file = "processed.json"  # File that tracks which PDFs are done

# Load existing processed data if file exists
if os.path.exists(processed_file):
    with open(processed_file, "r") as f:
        processed_data = json.load(f)
else:
    processed_data = {}  # Start fresh if no tracking file exists

new_found = False  # Flag to track if any new PDFs were found

# Loop through all files in the pdfs/ folder
for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf") and filename not in processed_data:
        # This is a new PDF — process it
        print(f"New PDF found, processing: {filename}")
        filepath = os.path.join(pdf_folder, filename)
        text = pdf_se_text_nikalo(filepath)       # Extract text
        points = key_points_nikalo(text)          # Get key points
        title = filename.replace('.pdf', '').replace('_', ' ').title()  # Clean up filename as title
        processed_data[filename] = {'title': title, 'points': points}
        new_found = True

# If new PDFs were found, save updated tracking file
if new_found:
    with open(processed_file, "w") as f:
        json.dump(processed_data, f)
    print("New PDF(s) processed and saved!")

# Always rebuild index.html so design/CSS changes apply without reprocessing PDFs
website_banao(list(processed_data.values()))
print("Website updated successfully!")