import sys
content = open('generate_market.py', 'r', encoding='utf-8').read()

m6_m8_cards = """
    # M6 components
    m6c = m6.get('signal_col', '#888')
    m6_card = f'''
    <div class="card">
        <div class="card-head">M6 — INSTITUTIONAL CONVICTION <span class="badge">5-DAY FLOWS</span></div>
        <div class="verdict-box" style="border-color:{m6c};">
            <div class="verdict-lbl">CONVICTION TREND</div>
            <div class="verdict-val" style="color:{m6c};">{m6.get('signal', 'N/A')}</div>
            <div class="verdict-detail">DII vs FII 5-day net positioning</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">DII 5-DAY NET</div>
                <div style="font-size:2.0em;font-weight:700;color:{fc(m6.get('dii_5d_net',0))};margin-top:8px;">{cr(m6.get('dii_5d_net',0))}</div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">FII 5-DAY NET</div>
                <div style="font-size:2.0em;font-weight:700;color:{fc(m6.get('fii_5d_net',0))};margin-top:8px;">{cr(m6.get('fii_5d_net',0))}</div>
            </div>
        </div>
    </div>'''

    # M8 components
    m8c = m8.get('signal_col', '#888')
    m8_card = f'''
    <div class="card">
        <div class="card-head">M8 — PROMOTER CONFIDENCE <span class="badge">INSIDER TRENDS</span></div>
        <div class="verdict-box" style="border-color:{m8c};">
            <div class="verdict-lbl">INSIDER SENTIMENT</div>
            <div class="verdict-val" style="color:{m8c};">{m8.get('signal', 'N/A')}</div>
            <div class="verdict-detail">Promoter bulk deals proxy</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">PROMOTER BUYS</div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">TRANSACTIONS</span><span style="color:#00cc44;font-weight:700;font-size:1.5em;">{m8.get('buy_count',0)}</span></div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">COMPANIES</span><span style="color:#fff;font-weight:700;font-size:1.1em;">{m8.get('companies',0)}</span></div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">PROMOTER SELLS</div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">TRANSACTIONS</span><span style="color:#ff3333;font-weight:700;font-size:1.5em;">{m8.get('sell_count',0)}</span></div>
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">COMPANIES</span><span style="color:#fff;font-weight:700;font-size:1.1em;">_</span></div>
            </div>
        </div>
    </div>'''

    m1c = m1['verdict_col']
"""

if 'm6_card =' not in content:
    content = content.replace("    m1c = m1['verdict_col']", m6_m8_cards)
    with open('generate_market.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed cards.")
else:
    print("Cards already present.")
