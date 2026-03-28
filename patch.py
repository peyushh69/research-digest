import sys
import os
import re

content = open('generate_market.py', 'r', encoding='utf-8').read()

m6_code = """
# ================================================================
#  M6: INSTITUTIONAL CONVICTION METER
# ================================================================

def process_m6():
    print("\\n" + "─"*50)
    print("[M6] Institutional Conviction Meter")
    print("─"*50)

    result = {
        'dii_5d_net': 0, 'fii_5d_net': 0,
        'dii_trend': 'FLAT', 'signal': 'NO DATA',
        'signal_col': '#888888', 'date': TODAY_STR,
    }

    cash_file = find('daily', [
        'fii-dii-combined-latest.csv','fii-dii*.csv',
        'fii_dii*.csv','FII_DII*.csv','FII*.csv'
    ])
    if not cash_file:
        print("  ✗ fii-dii-combined-latest.csv not found")
        return result

    rows = read_csv(cash_file)
    dii_flows, fii_flows = [], []
    for r in rows:
        cat_key = next((k for k in r if 'CATEGORY' in k.upper()), None)
        net_key = next((k for k in r if 'NET' in k.upper()), None)
        dt_key  = next((k for k in r if 'DATE' in k.upper()), None)
        if not cat_key or not net_key: continue
        cat = r[cat_key].strip().strip('"').upper()
        net = num(r.get(net_key, 0))
        if 'DII' in cat: dii_flows.append(net)
        if 'FII' in cat or 'FPI' in cat: fii_flows.append(net)

    # Assumes rows are newest first or similar. Just take up to 5 entries.
    dii_5d = sum(dii_flows[:5])
    fii_5d = sum(fii_flows[:5])
    result['dii_5d_net'] = dii_5d
    result['fii_5d_net'] = fii_5d

    dii_increasing = len(dii_flows) >= 2 and dii_flows[0] > dii_flows[1]

    if dii_5d > 0 and dii_increasing:
        result.update({'signal': 'Strong Conviction', 'signal_col': '#00cc44'})
        print("  DII buying increasing -> Strong Conviction")
    elif dii_5d > 0 and fii_5d < 0:
        result.update({'signal': 'DII Absorbing', 'signal_col': '#ff9944'})
        print("  DII absorbing FII selling")
    elif dii_5d > 0 and fii_5d > 0:
        result.update({'signal': 'Rally Support', 'signal_col': '#00ff88'})
        print("  Both DII and FII buying -> Rally Support")
    else:
        result.update({'signal': 'Weak Conviction', 'signal_col': '#ff3333'})
        print("  Weak Conviction")

    print(f"  M6 DII 5d: {dii_5d:+.0f} | FII 5d: {fii_5d:+.0f}")
    return result

# ================================================================
#  M8: PROMOTER CONFIDENCE INDEX
# ================================================================

def process_m8():
    print("\\n" + "─"*50)
    print("[M8] Promoter Confidence Index")
    print("─"*50)

    result = {
        'buy_count': 0, 'sell_count': 0, 'companies': 0,
        'signal': 'NO DATA', 'signal_col': '#888888', 'date': TODAY_STR,
    }

    bulk_file = find('daily', ['bulk*.csv', 'insider*.csv'])
    if not bulk_file:
        print("  ✗ bulk.csv not found")
        return result

    print(f"  Bulk file: {os.path.basename(bulk_file)}")
    rows = read_csv(bulk_file)
    buys, sells = 0, 0
    bought_companies = set()

    for r in rows:
        client = str(r.get('Client Name', r.get('CLIENT NAME', ''))).upper()
        if 'PROMOTER' in client or 'DIRECTOR' in client:
            ttype = str(r.get('Buy/Sell', r.get('BUY/SELL', ''))).upper()
            sym   = str(r.get('Symbol', r.get('SYMBOL', ''))).upper()
            if 'BUY' in ttype or ttype == 'B':
                buys += 1
                bought_companies.add(sym)
            elif 'SELL' in ttype or ttype == 'S':
                sells += 1

    result['buy_count'] = buys
    result['sell_count']  = sells
    result['companies']   = len(bought_companies)

    if len(bought_companies) >= 3:
        result.update({'signal': 'Bottom Signal (Cluster)', 'signal_col': '#00cc44'})
    elif sells > buys:
        result.update({'signal': 'Distribution Phase', 'signal_col': '#ff3333'})
    elif buys > sells:
        result.update({'signal': 'Accumulation', 'signal_col': '#00ff88'})
    else:
        result.update({'signal': 'Neutral', 'signal_col': '#888888'})

    print(f"  M8 Promoters: Buys: {buys} | Sells: {sells} | Signal: {result['signal']}")
    return result
"""

html_injection = "def build_html(m1, m4, m6, m7, m8):"

card_m6_m8 = """
    # M6 components
    m6c = m6['signal_col']
    m6_card = f'''
    <div class="card">
        <div class="card-head">M6 — INSTITUTIONAL CONVICTION <span class="badge">5-DAY FLOWS</span></div>
        <div class="verdict-box" style="border-color:{m6c};">
            <div class="verdict-lbl">CONVICTION TREND</div>
            <div class="verdict-val" style="color:{m6c};">{m6['signal']}</div>
            <div class="verdict-detail">DII vs FII 5-day net positioning</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">DII 5-DAY NET</div>
                <div style="font-size:2.0em;font-weight:700;color:{fc(m6['dii_5d_net'])};margin-top:8px;">{cr(m6['dii_5d_net'])}</div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">FII 5-DAY NET</div>
                <div style="font-size:2.0em;font-weight:700;color:{fc(m6['fii_5d_net'])};margin-top:8px;">{cr(m6['fii_5d_net'])}</div>
            </div>
        </div>
    </div>'''

    # M8 components
    m8c = m8['signal_col']
    m8_card = f'''
    <div class="card">
        <div class="card-head">M8 — PROMOTER CONFIDENCE <span class="badge">INSIDER TRENDS</span></div>
        <div class="verdict-box" style="border-color:{m8c};">
            <div class="verdict-lbl">INSIDER SENTIMENT</div>
            <div class="verdict-val" style="color:{m8c};">{m8['signal']}</div>
            <div class="verdict-detail">Promoter bulk deals proxy</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">PROMOTER BUYS</div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">TRANSACTIONS</span><span style="color:#00cc44;font-weight:700;font-size:1.5em;">{m8['buy_count']}</span></div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">COMPANIES</span><span style="color:#fff;font-weight:700;font-size:1.1em;">{m8['companies']}</span></div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">PROMOTER SELLS</div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">TRANSACTIONS</span><span style="color:#ff3333;font-weight:700;font-size:1.5em;">{m8['sell_count']}</span></div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">COMPANIES</span><span style="color:#fff;font-weight:700;font-size:1.1em;">{m8['companies']}</span></div>
            </div>
        </div>
    </div>'''
"""

if 'def process_m6' not in content:
    content = content.replace('#  HTML BUILDER', m6_code + '\n#  HTML BUILDER')
    content = content.replace('def build_html(m1, m4, m7):', html_injection)
    content = content.replace('    m1c = m1[\'verdict_col\']', card_m6_m8 + '\n    m1c = m1[\'verdict_col\']')
    content = content.replace('    {m7_card}', '    {m6_card}\n    {m7_card}\n    {m8_card}')
    content = content.replace('''    m7 = process_m7()''', '''    m6 = process_m6()\n    m7 = process_m7()\n    m8 = process_m8()''')
    content = content.replace('build_html(m1, m4, m7)', 'build_html(m1, m4, m6, m7, m8)')
    content = content.replace("'m7':m7,'date':TODAY_STR}", "'m6':m6,'m7':m7,'m8':m8,'date':TODAY_STR}")
    
    with open('generate_market.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully again!")
else:
    print("Already patched.")

