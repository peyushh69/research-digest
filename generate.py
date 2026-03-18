import fitz
import os
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from datetime import datetime

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

def pdf_se_text_nikalo(filepath):
    doc = fitz.open(filepath)
    poora_text = ""
    for page in doc:
        poora_text += page.get_text()
    doc.close()
    return poora_text

def key_points_nikalo(text, kitne_points=5):
    clean_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if '@' in line:
            continue
        if len(line) < 60:
            continue
        if len(line) > 200:
            continue
        if any(word in line.lower() for word in [
            'disclaimer', 'views expressed', 'do not necessarily',
            'reflect the views', 'personal views', 'author',
            'nothing contained', 'shall constitute', 'solicitation',
            'offer to sell', 'offer to purchase', 'securities',
            'invitation or solicitation', 'any entity'
        ]):
            continue
        clean_lines.append(line)

    clean_text = ' '.join(clean_lines)
    parser = PlaintextParser.from_string(clean_text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, kitne_points)
    return [str(sentence) for sentence in summary]

def website_banao(reports_data):
    aaj_ki_tarikh = datetime.today().strftime('%d %B %Y')
    
    all_cards = ""
    for report in reports_data:
        points_html = "".join(f"        <li>{p}</li>\n" for p in report['points'])
        all_cards += f"""
    <div class="report-card">
        <h2>{report['title']}</h2>
        <div class="date">Processed on: {aaj_ki_tarikh}</div>
        <ul>
{points_html}        </ul>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Research Digest</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 860px; margin: 40px auto; padding: 0 20px; background: #f9f9f9; color: #222; }}
        h1 {{ font-size: 1.8em; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .report-card {{ background: white; border-left: 4px solid #2c5f8a; padding: 20px 30px; margin: 30px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
        .report-card h2 {{ font-size: 1.2em; color: #2c5f8a; margin-bottom: 5px; }}
        .date {{ font-size: 0.85em; color: #888; margin-bottom: 15px; }}
        ul {{ line-height: 1.9; padding-left: 20px; }}
        li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <h1>📊 Research Digest</h1>
    {all_cards}
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html update ho gayi!")

# --- Main Process ---
import json

pdf_folder = "pdfs"
processed_file = "processed.json"

# Pehle se processed PDFs ki list load karo
if os.path.exists(processed_file):
    with open(processed_file, "r") as f:
        processed_data = json.load(f)
else:
    processed_data = {}

new_found = False

for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf") and filename not in processed_data:
        print(f"New PDF mili, processing: {filename}")
        filepath = os.path.join(pdf_folder, filename)
        text = pdf_se_text_nikalo(filepath)
        points = key_points_nikalo(text)
        title = filename.replace('.pdf', '').replace('_', ' ').title()
        processed_data[filename] = {'title': title, 'points': points}
        new_found = True

if new_found:
    # Save updated tracking file
    with open(processed_file, "w") as f:
        json.dump(processed_data, f)
    website_banao(list(processed_data.values()))
    print("Website update ho gayi!")
else:
    print("Koi nayi PDF nahi mili. Website unchanged.")