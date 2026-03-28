# ================================================================
#  QUANTIS — generate_market.py
#  M1: Smart Money Divergence
#  M4: Sector Money Flow
#  M7: Leverage & Risk Meter
#
#  Folder structure:
#  market-data/
#  ├── daily/
#  │   ├── fii-dii-combined-latest.csv   ← NSE FII/DII cash
#  │   ├── fii_stats_*.xls               ← NSE FII derivatives
#  │   └── bhavcopy_csv.csv              ← NSE EOD bhavcopy
#  └── weekly/
#      ├── fao_participant_oi_*.csv      ← NSE participant OI
#      └── fo_ban_csv.csv               ← NSE F&O ban list
#
#  Run: python generate_market.py
#  Output: market.html
# ================================================================

import os, glob, csv, json
from datetime import datetime, date

DATA_FOLDER  = "market-data"
OUTPUT_FILE  = "market.html"
TODAY_STR    = datetime.today().strftime('%d %b %Y').upper()

# ================================================================
#  SECTION 1: FILE FINDER
#  Folder mein latest matching file dhundho
# ================================================================

def find(folder, patterns):
    """market-data/daily/ ya market-data/weekly/ mein file dhundho"""
    base = os.path.join(DATA_FOLDER, folder)
    for p in patterns:
        files = glob.glob(os.path.join(base, p))
        if files:
            return sorted(files)[-1]
    return None

# ================================================================
#  SECTION 2: FILE READERS
# ================================================================

def read_csv(fp):
    """CSV file padhta hai — multiple encodings try karta hai"""
    for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
        try:
            with open(fp, 'r', encoding=enc) as f:
                rows = list(csv.DictReader(f))
                # Clean column names (strip whitespace + newlines)
                clean = []
                for row in rows:
                    clean.append({k.strip().replace('\n','').replace('\r',''):
                                  str(v).strip() for k, v in row.items()})
                return clean
        except:
            continue
    return []

def read_xls(fp):
    """XLS file padhta hai — xlrd se"""
    try:
        import xlrd
        wb   = xlrd.open_workbook(fp)
        ws   = wb.sheet_by_index(0)
        hdrs = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
        rows = []
        for r in range(1, ws.nrows):
            row = {hdrs[c]: str(ws.cell_value(r, c)).strip() for c in range(ws.ncols)}
            rows.append(row)
        return rows
    except ImportError:
        print("  Install: pip install xlrd")
        return []
    except Exception as e:
        print(f"  XLS error: {e}")
        return []

def num(val):
    """String → float"""
    try:
        return float(str(val).replace(',','').replace('(', '-')
                              .replace(')','').replace('₹','').strip() or 0)
    except:
        return 0.0

# ================================================================
#  M1: SMART MONEY DIVERGENCE
#  Files: daily/fii-dii-combined-latest.csv
#         daily/fii_stats_*.xls
#
#  Column names (confirmed from your files):
#  fii-dii CSV: CATEGORY, DATE, BUY VALUE (₹ Crores),
#               SELL VALUE (₹ Crores), NET VALUE (₹ Crores)
#  fii_stats XLS: Date, Instrument Type, Buy Amount,
#                 Sell Amount, Net Amount
# ================================================================

def process_m1():
    print("\n[M1] Smart Money Divergence...")

    result = {
        'cash':      {'buy': 0, 'sell': 0, 'net': 0},
        'dii_cash':  {'buy': 0, 'sell': 0, 'net': 0},
        'index_fut': {'long': 0, 'short': 0, 'net': 0},
        'stock_fut': {'long': 0, 'short': 0, 'net': 0},
        'index_opt': {'net': 0},
        'stock_opt': {'net': 0},
        'date':      TODAY_STR,
        'verdict':   'NO DATA',
        'verdict_col': '#888',
        'verdict_detail': 'Add fii-dii-combined-latest.csv and fii_stats.xls to market-data/daily/',
        'risk': 'UNKNOWN',
        'cash_dir': '─',
        'fut_dir':  '─',
        'total_net': 0,
    }

    # ── FII/DII Cash ──
    # File: market-data/daily/fii-dii-combined-latest.csv
    # Columns: CATEGORY | DATE | BUY VALUE (₹ Crores) |
    #          SELL VALUE (₹ Crores) | NET VALUE (₹ Crores)
    cash_file = find('daily', [
        'fii-dii-combined-latest.csv',
        'fii-dii*.csv', 'fii_dii*.csv', 'FII_DII*.csv'
    ])
    if cash_file:
        rows = read_csv(cash_file)
        print(f"  Cash: {os.path.basename(cash_file)} ({len(rows)} rows)")
        for row in rows:
            cat = str(row.get('CATEGORY', row.get('Category', ''))).upper().strip()
            buy = num(row.get('BUY VALUE (₹ Crores)',
                      row.get('Buy Value', row.get('BUY VALUE', 0))))
            sel = num(row.get('SELL VALUE (₹ Crores)',
                      row.get('Sell Value', row.get('SELL VALUE', 0))))
            net = num(row.get('NET VALUE (₹ Crores)',
                      row.get('Net Value', row.get('NET VALUE', buy - sel))))
            dt  = str(row.get('DATE', row.get('Date', ''))).strip()
            if dt:
                result['date'] = dt.upper()

            if 'FII' in cat or 'FPI' in cat:
                result['cash'] = {'buy': buy, 'sell': sel, 'net': net}
                print(f"  FII Cash — Buy:{buy:,.0f}  Sell:{sel:,.0f}  Net:{net:+,.0f}")
            elif 'DII' in cat:
                result['dii_cash'] = {'buy': buy, 'sell': sel, 'net': net}
                print(f"  DII Cash — Buy:{buy:,.0f}  Sell:{sel:,.0f}  Net:{net:+,.0f}")
    else:
        print("  ✗ fii-dii-combined-latest.csv not found in market-data/daily/")

    # ── FII Derivatives (XLS) ──
    # File: market-data/daily/fii_stats_*.xls
    # Columns: Date | Instrument Type | Buy Amount |
    #          Sell Amount | Net Amount
    deriv_file = find('daily', [
        'fii_stats*.xls', 'fii_stats*.xlsx',
        'fii_stats*.csv', 'fii-stats*.xls',
        'FII*stat*.xls',  'FII*deriv*.xls'
    ])
    if deriv_file:
        ext  = os.path.splitext(deriv_file)[1].lower()
        rows = read_xls(deriv_file) if ext in ['.xls','.xlsx'] else read_csv(deriv_file)
        print(f"  Derivatives: {os.path.basename(deriv_file)} ({len(rows)} rows)")
        if rows:
            print(f"  Columns: {list(rows[0].keys())[:5]}")

        for row in rows:
            inst = str(row.get('Instrument Type',
                       row.get('instrument_type',
                       row.get('Category', '')))).upper().strip()
            buy  = num(row.get('Buy Amount', row.get('Buy Value', 0)))
            sel  = num(row.get('Sell Amount', row.get('Sell Value', 0)))
            net  = num(row.get('Net Amount', row.get('Net Value', buy - sel)))

            if any(x in inst for x in ['FUTIDX','INDEX FUT','INDEX FUTURES']):
                result['index_fut'] = {'long': buy, 'short': sel, 'net': net}
                print(f"  Idx Fut — Long:{buy:,.0f}  Short:{sel:,.0f}  Net:{net:+,.0f}")
            elif any(x in inst for x in ['FUTSTK','STOCK FUT','STOCK FUTURES']):
                result['stock_fut'] = {'long': buy, 'short': sel, 'net': net}
                print(f"  Stk Fut — Long:{buy:,.0f}  Short:{sel:,.0f}  Net:{net:+,.0f}")
            elif any(x in inst for x in ['OPTIDX','INDEX OPT','INDEX OPTIONS']):
                result['index_opt'] = {'net': net}
            elif any(x in inst for x in ['OPTSTK','STOCK OPT','STOCK OPTIONS']):
                result['stock_opt'] = {'net': net}
    else:
        print("  ✗ fii_stats.xls not found in market-data/daily/")

    # ── Verdict Logic ──
    cash_net = result['cash']['net']
    fut_net  = result['index_fut']['net'] + result['stock_fut']['net']
    cash_dir = 'BUY'  if cash_net >= 0 else 'SELL'
    fut_dir  = 'LONG' if fut_net  >= 0 else 'SHORT'

    combos = {
        ('SELL','LONG'):  ('HEDGE',               '#4488ff','LOW',
                           'Cash sell lekin futures LONG — FII hedge kar raha hai, exit nahi. Market nahi girega much.'),
        ('SELL','SHORT'): ('REAL EXIT',            '#ff3333','HIGH',
                           'Cash sell + futures SHORT — Genuine bearish exit. Fresh longs avoid karo.'),
        ('BUY', 'LONG'):  ('AGGRESSIVE ACCUMULATE','#00cc44','VERY LOW',
                           'Cash buy + futures LONG — Strong bullish conviction. FII accumulate kar raha hai.'),
        ('BUY', 'SHORT'): ('PROFIT BOOKING',       '#ff9944','MEDIUM',
                           'Cash buy lekin futures SHORT — Profit book kar raha hai ya longs hedge kar raha hai.'),
    }
    v, vc, risk, detail = combos.get(
        (cash_dir, fut_dir),
        ('NEUTRAL','#888','NEUTRAL','No clear FII directional bias today.'))

    result.update({
        'verdict': v, 'verdict_col': vc, 'verdict_detail': detail,
        'risk': risk, 'cash_dir': cash_dir, 'fut_dir': fut_dir,
        'total_net': cash_net + fut_net + result['index_opt']['net'],
    })
    print(f"\n  M1: {v} | Cash:{cash_dir} | Fut:{fut_dir} | Risk:{risk}")
    return result

# ================================================================
#  M4: SECTOR MONEY FLOW
#  File: daily/bhavcopy_csv.csv
#
#  Confirmed columns:
#  SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE,
#  LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY,
#  TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
# ================================================================

SECTORS = {
    'IT':       ['TCS','INFY','WIPRO','HCLTECH','TECHM','LTIM','MPHASIS','PERSISTENT'],
    'BANKING':  ['HDFCBANK','ICICIBANK','KOTAKBANK','SBIN','AXISBANK','INDUSINDBK','BANDHANBNK'],
    'AUTO':     ['MARUTI','TATAMOTORS','BAJAJ-AUTO','HEROMOTOCO','EICHERMOT','M&M','TVSMOTOR'],
    'PHARMA':   ['SUNPHARMA','DRREDDY','CIPLA','DIVISLAB','APOLLOHOSP','AUROPHARMA'],
    'METALS':   ['TATASTEEL','JSWSTEEL','HINDALCO','VEDL','COALINDIA','SAIL','NMDC'],
    'ENERGY':   ['RELIANCE','ONGC','NTPC','POWERGRID','BPCL','IOC','TATAPOWER','ADANIGREEN'],
    'FMCG':     ['HINDUNILVR','ITC','NESTLEIND','BRITANNIA','DABUR','GODREJCP','MARICO'],
    'FINANCE':  ['BAJFINANCE','BAJAJFINSV','SBILIFE','HDFCLIFE','ICICIPRULI','CHOLAFIN'],
    'INFRA':    ['LT','ADANIENT','ADANIPORTS','DLF','ULTRACEMCO','GRASIM'],
    'TELECOM':  ['BHARTIARTL','IDEA','INDUSTOWER'],
}

def process_m4():
    print("\n[M4] Sector Money Flow...")

    result = {
        'sectors':   {},
        'top_3':     [],
        'bottom_3':  [],
        'risk_mode': 'NO DATA',
        'signal':    'Add bhavcopy_csv.csv to market-data/daily/',
        'signal_col':'#888',
        'advances':  0,
        'declines':  0,
        'unchanged': 0,
        'avg_delivery': 0,
        'date':      TODAY_STR,
    }

    # File: market-data/daily/bhavcopy_csv.csv
    bhav = find('daily', [
        'bhavcopy_csv.csv', 'bhavcopy*.csv',
        'cm*bhav.csv', 'NSE_CM*.csv', 'EQUITY*.csv'
    ])
    if not bhav:
        print("  ✗ bhavcopy_csv.csv not found in market-data/daily/")
        return result

    rows = read_csv(bhav)
    print(f"  Bhavcopy: {os.path.basename(bhav)} ({len(rows)} rows)")

    stock_perf = {}
    deliveries = []
    adv = dec = unch = 0

    for row in rows:
        sym    = str(row.get('SYMBOL', '')).strip()
        series = str(row.get('SERIES', '')).strip()
        if series not in ['EQ', 'BE']:
            continue
        try:
            close = num(row.get('CLOSE_PRICE', row.get('CLOSE', 0)))
            prev  = num(row.get('PREV_CLOSE',  row.get('PREVCLOSE', 0)))
            deliv = num(row.get('DELIV_PER',   row.get('DELIVERY_PER', 0)))

            if close > 0 and prev > 0:
                pct = round(((close - prev) / prev) * 100, 2)
                stock_perf[sym] = pct
                if pct >  0.05: adv  += 1
                elif pct < -0.05: dec += 1
                else: unch += 1
                if deliv > 0:
                    deliveries.append(deliv)
        except:
            continue

    result['advances']  = adv
    result['declines']  = dec
    result['unchanged'] = unch
    result['avg_delivery'] = round(sum(deliveries)/len(deliveries), 1) if deliveries else 0

    # Sector averages
    sector_perf = {}
    for sector, stocks in SECTORS.items():
        vals = [stock_perf[s] for s in stocks if s in stock_perf]
        if vals:
            sector_perf[sector] = round(sum(vals)/len(vals), 2)
            print(f"  {sector:10}: {sector_perf[sector]:+.2f}%  ({len(vals)}/{len(stocks)})")

    result['sectors'] = sector_perf

    if sector_perf:
        ranked = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
        result['top_3']   = ranked[:3]
        result['bottom_3']= ranked[-3:][::-1]

        def_score = sum(sector_perf.get(s, 0) for s in ['PHARMA','IT','FMCG'])
        cyc_score = sum(sector_perf.get(s, 0) for s in ['AUTO','METALS','ENERGY','BANKING'])

        if cyc_score > def_score + 1:
            result.update({'risk_mode':'RISK-ON', 'signal_col':'#00cc44',
                           'signal':'Cyclicals lead — RISK-ON mode'})
        elif def_score > cyc_score + 1:
            result.update({'risk_mode':'RISK-OFF', 'signal_col':'#4488ff',
                           'signal':'Defensives lead — RISK-OFF mode'})
        else:
            result.update({'risk_mode':'MIXED', 'signal_col':'#888',
                           'signal':'No clear sector rotation'})

    ad_ratio = round(adv/dec, 2) if dec > 0 else adv
    print(f"\n  M4: {result['risk_mode']} | A/D:{adv}/{dec} | Delivery:{result['avg_delivery']}%")
    return result

# ================================================================
#  M7: LEVERAGE & RISK METER
#  Files: weekly/fao_participant_oi_*.csv
#         weekly/fo_ban_csv.csv
#
#  Confirmed columns (participant OI):
#  Client Type | Future Index Long | Future Index Short |
#  Future Stock Long | Future Stock Short |
#  Option Index Call Long | ... | Total Long | Total Short
#
#  fo_ban format:
#  Line 1: "Securities in Ban For Trade Date DD-MMM-YYYY:"
#  Then: "1,SYMBOL"
# ================================================================

def process_m7():
    print("\n[M7] Leverage & Risk Meter...")

    result = {
        'ban_count':   0,
        'ban_stocks':  [],
        'ban_date':    '',
        'fii_idx_long':  0,
        'fii_idx_short': 0,
        'fii_stk_long':  0,
        'fii_stk_short': 0,
        'fii_ls_ratio':  0,
        'fii_signal':    'NO DATA',
        'risk_level':    'UNKNOWN',
        'risk_col':      '#888',
        'risk_detail':   'Add fo_ban_csv.csv and fao_participant_oi.csv to market-data/weekly/',
        'date':          TODAY_STR,
    }

    # ── F&O Ban List ──
    # File: market-data/weekly/fo_ban_csv.csv
    # Format: Line1 = header with date, then "1,SYMBOL"
    ban_file = find('weekly', [
        'fo_ban_csv.csv', 'fo_ban*.csv',
        'ban*.csv', '*ban*list*.csv'
    ])
    if ban_file:
        ban_stocks = []
        ban_date   = ''
        with open(ban_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if 'Securities in Ban' in line or 'Ban For Trade' in line:
                    # Extract date from header line
                    parts = line.split(':')
                    if len(parts) > 0:
                        ban_date = parts[0].replace('Securities in Ban For Trade Date','').strip()
                    continue
                # Lines like "1,SAIL" or just "SAIL"
                parts = line.split(',')
                if len(parts) >= 2:
                    sym = parts[1].strip()
                elif len(parts) == 1:
                    sym = parts[0].strip()
                else:
                    continue
                if sym and not sym.isdigit() and sym not in ['', 'SYMBOL']:
                    ban_stocks.append(sym)

        result['ban_count']  = len(ban_stocks)
        result['ban_stocks'] = ban_stocks
        result['ban_date']   = ban_date
        print(f"  Ban list ({ban_date}): {len(ban_stocks)} stocks — {', '.join(ban_stocks[:10])}")
    else:
        print("  ✗ fo_ban_csv.csv not found in market-data/weekly/")

    # ── Participant OI ──
    # File: market-data/weekly/fao_participant_oi_*.csv
    # Confirmed columns:
    # Client Type | Future Index Long | Future Index Short |
    # Future Stock Long | Future Stock Short | ... | Total Long | Total Short
    oi_file = find('weekly', [
        'fao_participant_oi*.csv', 'participant_oi*.csv',
        'Participant_OI*.csv', '*participant*oi*.csv'
    ])
    if oi_file:
        rows = read_csv(oi_file)
        print(f"  Participant OI: {os.path.basename(oi_file)} ({len(rows)} rows)")

        fii_il = fii_is = fii_sl = fii_ss = 0
        client_il = client_is = 0
        pro_il    = pro_is    = 0

        for row in rows:
            cat = str(row.get('Client Type', row.get('Participant', ''))).upper().strip()
            if not cat or cat == 'TOTAL':
                continue

            il = num(row.get('Future Index Long',  0))
            is_= num(row.get('Future Index Short', 0))
            sl = num(row.get('Future Stock Long',  0))
            ss = num(row.get('Future Stock Short', 0))

            if cat == 'FII' or 'FPI' in cat:
                fii_il = il; fii_is = is_; fii_sl = sl; fii_ss = ss
                print(f"  FII — Idx L:{il:,.0f} S:{is_:,.0f} | Stk L:{sl:,.0f} S:{ss:,.0f}")
            elif cat == 'CLIENT':
                client_il = il; client_is = is_
            elif cat == 'PRO':
                pro_il = il; pro_is = is_

        result.update({
            'fii_idx_long':  fii_il,
            'fii_idx_short': fii_is,
            'fii_stk_long':  fii_sl,
            'fii_stk_short': fii_ss,
        })

        total_long  = fii_il + fii_sl
        total_short = fii_is + fii_ss
        if total_short > 0:
            result['fii_ls_ratio'] = round(total_long / total_short, 2)

        ratio = result['fii_ls_ratio']
        if ratio > 1.3:
            result['fii_signal'] = 'FII NET LONG'
        elif ratio > 0.9:
            result['fii_signal'] = 'FII NEUTRAL'
        elif ratio > 0:
            result['fii_signal'] = 'FII NET SHORT'
    else:
        print("  ✗ fao_participant_oi.csv not found in market-data/weekly/")

    # ── Risk Score ──
    ban   = result['ban_count']
    ratio = result['fii_ls_ratio']
    score = 0

    if ban > 15:   score += 3
    elif ban > 8:  score += 2
    elif ban > 3:  score += 1

    if   ratio > 0 and ratio < 0.7: score += 3
    elif ratio > 0 and ratio < 1.0: score += 1
    elif ratio > 1.5:               score -= 1

    if score >= 4:
        result.update({'risk_level':'VERY HIGH','risk_col':'#ff2222',
            'risk_detail':f'Ban {ban} stocks + FII heavily short. Avoid leveraged positions.'})
    elif score >= 2:
        result.update({'risk_level':'ELEVATED','risk_col':'#ff9944',
            'risk_detail':f'Ban {ban} stocks. Elevated leverage. Use smaller sizes.'})
    elif score >= 0:
        result.update({'risk_level':'NORMAL','risk_col':'#00cc44',
            'risk_detail':f'Ban {ban} stocks. Leverage within normal range.'})
    else:
        result.update({'risk_level':'LOW','risk_col':'#00ff88',
            'risk_detail':f'FII net long. Low leverage. Favorable for longs.'})

    print(f"\n  M7: Risk:{result['risk_level']} | Ban:{ban} | L/S:{result['fii_ls_ratio']}")
    return result

# ================================================================
#  HTML BUILDER — market.html
#  Same style as your index.html (black, IBM Plex Mono, orange)
# ================================================================

def build_html(m1, m4, m7):
    def fc(v):   return '#00cc44' if v > 0 else ('#ff3333' if v < 0 else '#888')
    def cr(v):   return f"{'+'if v>=0 else ''}₹{abs(v):,.0f} Cr"
    def pct_html(v):
        c = '#00cc44' if v > 0 else ('#ff3333' if v < 0 else '#888')
        s = '+' if v > 0 else ''
        a = '▲' if v > 0 else ('▼' if v < 0 else '─')
        return f'<span style="color:{c};font-weight:700;">{a} {s}{v:.2f}%</span>'

    # ── M1 HTML ──
    c   = m1['cash']
    di  = m1['dii_cash']
    fi  = m1['index_fut']
    fs  = m1['stock_fut']
    io  = m1['index_opt']

    dii_row = ''
    if di.get('net', 0) != 0:
        dii_row = f'''
        <div class="data-row">
            <div>
                <div class="lbl">DII NET <span class="sub">(Buy ₹{di['buy']:,.0f} · Sell ₹{di['sell']:,.0f})</span></div>
            </div>
            <div class="val" style="color:{fc(di['net'])}">{cr(di['net'])}</div>
        </div>'''

    m1_html = f'''
    <div class="card">
        <div class="card-head">M1 — SMART MONEY DIVERGENCE <span class="badge">FII CASH + F&O</span></div>
        <div class="verdict-box" style="border-color:{m1['verdict_col']}">
            <div class="verdict-lbl">FII REAL INTENT</div>
            <div class="verdict-val" style="color:{m1['verdict_col']}">{m1['verdict']}</div>
            <div class="verdict-detail">{m1['verdict_detail']}</div>
        </div>
        <div class="grid2">
            <div class="inner">
                <div class="inner-head">FII CASH EQUITY</div>
                <div class="data-row"><span class="lbl">BUY</span><span style="color:#00cc44;font-weight:700;">₹{c['buy']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SELL</span><span style="color:#ff3333;font-weight:700;">₹{c['sell']:,.0f} Cr</span></div>
                <div class="data-row" style="border:none"><span class="lbl fw">NET</span><span style="color:{fc(c['net'])};font-weight:700;">{cr(c['net'])}</span></div>
                <div class="pill" style="color:{fc(c['net'])}">{m1['cash_dir']}</div>
            </div>
            <div class="inner">
                <div class="inner-head">INDEX FUTURES</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">₹{fi['long']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">₹{fi['short']:,.0f} Cr</span></div>
                <div class="data-row" style="border:none"><span class="lbl fw">NET</span><span style="color:{fc(fi['net'])};font-weight:700;">{cr(fi['net'])}</span></div>
                <div class="pill" style="color:{fc(fi['net'])}">{m1['fut_dir']}</div>
            </div>
            <div class="inner">
                <div class="inner-head">STOCK FUTURES</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">₹{fs['long']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">₹{fs['short']:,.0f} Cr</span></div>
                <div class="data-row" style="border:none"><span class="lbl fw">NET</span><span style="color:{fc(fs['net'])};font-weight:700;">{cr(fs['net'])}</span></div>
            </div>
            <div class="inner">
                <div class="inner-head">SUMMARY</div>
                <div class="data-row"><span class="lbl">INDEX OPT NET</span><span style="color:{fc(io['net'])};font-weight:700;">{cr(io['net'])}</span></div>
                <div class="data-row"><span class="lbl">TOTAL NET</span><span style="color:{fc(m1['total_net'])};font-weight:700;">{cr(m1['total_net'])}</span></div>
                <div class="data-row" style="border:none"><span class="lbl">RISK</span><span style="color:#888;font-weight:700;">{m1['risk']}</span></div>
            </div>
        </div>
        {dii_row}
        <div class="hint">
            Cash SELL + Fut LONG = HEDGE — FII nahi nikal raha (Oct 2021 pattern)<br>
            Cash SELL + Fut SHORT = REAL EXIT — Genuine exit, avoid fresh longs<br>
            Cash BUY + Fut LONG = ACCUMULATE — Strong bullish signal<br>
            Data: {m1['date']}
        </div>
    </div>'''

    # ── M4 HTML ──
    sectors = m4.get('sectors', {})
    ranked  = sorted(sectors.items(), key=lambda x: x[1], reverse=True)

    sector_bars = ''
    for s, v in ranked:
        c_     = '#00cc44' if v > 0 else '#ff3333'
        bw     = min(110, abs(v) * 22)
        arrow  = '▲' if v > 0 else '▼'
        sign   = '+' if v > 0 else ''
        sector_bars += f'''
            <div class="sector-row">
                <span class="s-name">{s}</span>
                <div class="s-bar-wrap"><div style="background:{c_};height:6px;width:{bw}px;border-radius:2px;"></div></div>
                <span style="color:{c_};font-size:0.75em;font-weight:700;width:65px;text-align:right;">{arrow}{sign}{v:.2f}%</span>
            </div>'''

    adv  = m4.get('advances', 0)
    dec  = m4.get('declines', 0)
    unch = m4.get('unchanged', 0)
    del_ = m4.get('avg_delivery', 0)
    del_c= '#00cc44' if del_ >= 45 else ('#ff9944' if del_ >= 30 else '#ff3333')

    top3    = ' · '.join(f'<span style="color:#00cc44">{s}</span>({v:+.2f}%)' for s,v in m4.get('top_3',[]))
    bottom3 = ' · '.join(f'<span style="color:#ff3333">{s}</span>({v:+.2f}%)' for s,v in m4.get('bottom_3',[]))

    m4_html = f'''
    <div class="card">
        <div class="card-head">M4 — SECTOR ROTATION MAP <span class="badge">BHAVCOPY</span></div>
        <div class="verdict-box" style="border-color:{m4['signal_col']}">
            <div class="verdict-lbl">MARKET MODE</div>
            <div class="verdict-val" style="color:{m4['signal_col']}">{m4['risk_mode']}</div>
            <div class="verdict-detail">{m4['signal']}</div>
        </div>
        <div style="margin-bottom:10px;">
            <div class="inner-head" style="margin-bottom:8px;">SECTOR PERFORMANCE TODAY</div>
            {sector_bars if sector_bars else '<div style="color:#333;font-size:0.75em;">Add bhavcopy_csv.csv to market-data/daily/</div>'}
        </div>
        <div class="grid2">
            <div class="inner">
                <div class="inner-head" style="color:#555;">MARKET BREADTH</div>
                <div class="data-row"><span class="lbl">ADVANCES</span><span style="color:#00cc44;font-weight:700;">{adv:,}</span></div>
                <div class="data-row"><span class="lbl">DECLINES</span><span style="color:#ff3333;font-weight:700;">{dec:,}</span></div>
                <div class="data-row" style="border:none"><span class="lbl">UNCHANGED</span><span style="color:#555;font-weight:700;">{unch:,}</span></div>
            </div>
            <div class="inner">
                <div class="inner-head" style="color:#555;">DELIVERY & LEADERS</div>
                <div class="data-row"><span class="lbl">AVG DELIVERY</span><span style="color:{del_c};font-weight:700;">{del_}%</span></div>
                <div style="font-size:0.72em;margin-top:6px;line-height:1.8;">
                    <div>▲ {top3 if top3 else '─'}</div>
                    <div>▼ {bottom3 if bottom3 else '─'}</div>
                </div>
            </div>
        </div>
        <div class="hint">
            IT + Pharma lead = RISK-OFF (defensive rotation)<br>
            Auto + Metal + Energy lead = RISK-ON (cyclical)<br>
            Banking lead = liquidity positive, rate cut expected<br>
            All down = broad selloff / capitulation
        </div>
    </div>'''

    # ── M7 HTML ──
    ban_pills = ''.join(
        f'<span class="ban-pill">{s}</span>'
        for s in m7.get('ban_stocks', []))

    ratio = m7['fii_ls_ratio']
    lsc   = '#00cc44' if ratio > 1.2 else ('#ff3333' if 0 < ratio < 0.8 else '#888')
    lsig  = m7.get('fii_signal', 'NO DATA')

    il = m7['fii_idx_long']
    is_= m7['fii_idx_short']
    sl = m7['fii_stk_long']
    ss = m7['fii_stk_short']

    m7_html = f'''
    <div class="card">
        <div class="card-head">M7 — LEVERAGE &amp; RISK METER <span class="badge">F&O STRESS</span></div>
        <div class="verdict-box" style="border-color:{m7['risk_col']}">
            <div class="verdict-lbl">MARKET RISK LEVEL</div>
            <div class="verdict-val" style="color:{m7['risk_col']}">{m7['risk_level']}</div>
            <div class="verdict-detail">{m7['risk_detail']}</div>
        </div>
        <div class="grid2">
            <div class="inner">
                <div class="inner-head">F&O BAN LIST</div>
                <div style="font-size:2.2em;font-weight:700;color:{m7['risk_col']};margin:4px 0;">{m7['ban_count']}</div>
                <div style="font-size:0.63em;color:#444;letter-spacing:1px;">STOCKS IN BAN {m7.get('ban_date','')}</div>
                <div style="font-size:0.68em;color:#333;margin-top:6px;line-height:1.7;">
                    3-5 = normal · 6-10 = watch<br>10+ = elevated risk
                </div>
            </div>
            <div class="inner">
                <div class="inner-head">FII INDEX FUTURES</div>
                <div class="data-row"><span class="lbl">LONG (contracts)</span><span style="color:#00cc44;font-weight:700;">{il:,.0f}</span></div>
                <div class="data-row"><span class="lbl">SHORT (contracts)</span><span style="color:#ff3333;font-weight:700;">{is_:,.0f}</span></div>
                <div class="data-row" style="border:none"><span class="lbl fw">L/S RATIO</span><span style="color:{lsc};font-weight:700;">{ratio if ratio > 0 else '─'}</span></div>
                <div class="pill" style="color:{lsc}">{lsig}</div>
            </div>
            <div class="inner" style="grid-column:span 2;">
                <div class="inner-head">FII STOCK FUTURES</div>
                <div style="display:flex;gap:24px;font-size:0.82em;">
                    <div><span class="lbl">LONG</span> <span style="color:#00cc44;font-weight:700;">{sl:,.0f}</span></div>
                    <div><span class="lbl">SHORT</span> <span style="color:#ff3333;font-weight:700;">{ss:,.0f}</span></div>
                    <div><span class="lbl">NET</span> <span style="color:{fc(sl-ss)};font-weight:700;">{sl-ss:+,.0f}</span></div>
                </div>
            </div>
        </div>
        <div style="margin-top:10px;">
            <div class="inner-head" style="margin-bottom:6px;">STOCKS IN F&O BAN</div>
            <div style="line-height:2.2;">
                {ban_pills if ban_pills else '<span style="color:#222;font-size:0.75em;">No stocks in ban today</span>'}
            </div>
        </div>
        <div class="hint">
            FII L/S &lt; 0.7 = heavy short = high crash risk<br>
            FII L/S &gt; 1.5 = heavily long = strong market support<br>
            Ban list 10+ stocks = high leverage / manipulation risk<br>
            Data: {m7.get('date', TODAY_STR)}
        </div>
    </div>'''

    # Ticker items for status bar
    m1_color = m1.get('verdict_col', '#888')
    m4_color = m4.get('signal_col', '#888')
    m7_color = m7.get('risk_col', '#888')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QUANTIS — Market Intelligence</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ font-family:'IBM Plex Mono',monospace; background:#000; color:#fff; padding-bottom:40px; font-size:12px; }}

        /* ── HEADER — same as index.html ── */
        #site-header {{
            background:#000; border-bottom:2px solid #ff6600;
            padding:14px 24px; display:flex; align-items:center;
            justify-content:space-between; position:sticky; top:0; z-index:100;
        }}
        #site-logo {{ font-size:1.6em; font-weight:700; color:#fff; letter-spacing:3px; }}
        .nav-tabs {{ display:flex; }}
        .nav-tab {{
            padding:6px 16px; font-size:0.7em; letter-spacing:2px;
            color:#555; cursor:pointer; border:1px solid transparent;
            font-family:'IBM Plex Mono',monospace; text-decoration:none;
        }}
        .nav-tab.active {{ color:#ff6600; border:1px solid #ff6600; }}
        .nav-tab:hover  {{ color:#888; }}

        /* ── TICKER — same as index.html ── */
        #ticker-bar {{
            background:#fff; color:#000; font-size:0.75em; font-weight:700;
            padding:5px 0; overflow:hidden; white-space:nowrap; border-bottom:1px solid #ddd;
        }}
        #ticker-content {{ display:inline-block; animation:scroll-ticker 90s linear infinite; padding-left:100%; }}
        #ticker-content span {{ margin-right:60px; color:#000; }}
        @keyframes scroll-ticker {{ 0%{{transform:translateX(0)}} 100%{{transform:translateX(-100%)}} }}

        /* ── STATUS BAR ── */
        #status {{
            background:#0a0a0a; border-bottom:1px solid #111;
            padding:5px 24px; display:flex; gap:24px; font-size:0.68em;
            letter-spacing:1px; align-items:center;
        }}
        .st {{ display:flex; gap:8px; align-items:center; }}
        .st-lbl {{ color:#333; }}

        /* ── MAIN GRID ── */
        #main {{ max-width:1200px; margin:20px auto; padding:0 24px; display:grid; grid-template-columns:1fr 1fr 1fr; gap:1px; background:#111; }}

        /* ── CARD ── */
        .card {{ background:#000; padding:16px 18px; }}
        .card-head {{
            font-size:0.63em; letter-spacing:2px; color:#444;
            border-bottom:1px solid #1a1a1a; padding-bottom:6px;
            margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;
        }}
        .badge {{ font-size:0.9em; padding:1px 6px; border:1px solid #1a1a1a; color:#333; letter-spacing:1px; }}

        /* ── VERDICT ── */
        .verdict-box {{
            border:1px solid #222; background:#060606;
            padding:12px 14px; margin-bottom:12px; text-align:center;
        }}
        .verdict-lbl   {{ font-size:0.6em; color:#333; letter-spacing:3px; margin-bottom:4px; }}
        .verdict-val   {{ font-size:1.3em; font-weight:700; letter-spacing:2px; margin-bottom:6px; }}
        .verdict-detail{{ font-size:0.65em; color:#444; line-height:1.6; }}

        /* ── INNER GRID ── */
        .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:1px; background:#111; margin-bottom:10px; }}
        .inner {{ background:#000; padding:10px 12px; }}
        .inner-head {{ font-size:0.62em; color:#444; letter-spacing:2px; margin-bottom:6px; }}

        /* ── DATA ROWS ── */
        .data-row {{
            display:flex; justify-content:space-between; align-items:center;
            padding:4px 0; border-bottom:1px solid #0d0d0d;
        }}
        .lbl {{ color:#555; font-size:0.82em; letter-spacing:1px; }}
        .fw  {{ font-weight:700; color:#888; }}
        .val {{ font-weight:700; }}
        .sub {{ color:#333; font-size:0.8em; margin-left:6px; }}

        /* ── PILL ── */
        .pill {{
            margin-top:6px; padding:3px 8px; background:#0a0a0a;
            border:1px solid #1a1a1a; text-align:center;
            font-size:0.63em; font-weight:700; letter-spacing:2px;
        }}

        /* ── SECTOR BARS ── */
        .sector-row {{ display:flex; align-items:center; gap:8px; padding:4px 0; border-bottom:1px solid #080808; }}
        .s-name      {{ color:#666; font-size:0.72em; width:78px; flex-shrink:0; }}
        .s-bar-wrap  {{ flex:1; background:#0a0a0a; height:6px; border-radius:2px; overflow:hidden; }}

        /* ── BAN PILLS ── */
        .ban-pill {{
            display:inline-block; padding:2px 8px; margin:2px;
            background:#0a0a0a; border:1px solid #1a1a1a;
            color:#ff9944; font-size:0.7em; letter-spacing:1px;
        }}

        /* ── HINT ── */
        .hint {{
            margin-top:10px; padding:7px 10px; background:#050505;
            font-size:0.62em; color:#252525; line-height:1.9; border-left:2px solid #0d0d0d;
        }}

        /* ── FOOTER ── */
        #footer {{
            background:#000; border-top:1px solid #111;
            padding:8px 24px; display:flex; justify-content:space-between;
            font-size:0.62em; color:#1a1a1a; letter-spacing:1px; margin-top:2px;
        }}

        @media(max-width:900px) {{
            #main {{ grid-template-columns:1fr; }}
        }}
    </style>
</head>
<body>

<!-- HEADER — same as your index.html -->
<div id="site-header">
    <div id="site-logo">QUANTIS</div>
    <div class="nav-tabs">
        <a class="nav-tab" href="index.html">REPORTS</a>
        <a class="nav-tab active" href="market.html">MARKET</a>
        <a class="nav-tab" href="economics.html">ECONOMICS</a>
    </div>
    <div style="font-size:0.63em;color:#2a2a2a;letter-spacing:2px;">{TODAY_STR}</div>
</div>

<!-- TICKER — same as your index.html (live data from generate.py) -->
<div id="ticker-bar">
    <div id="ticker-content">
        <span>NIFTY 50 &nbsp; -- &nbsp; ─</span>
        <span>SENSEX &nbsp; -- &nbsp; ─</span>
        <span>BANK NIFTY &nbsp; -- &nbsp; ─</span>
        <span>RUN generate.py FOR LIVE DATA</span>
        <span>NIFTY 50 &nbsp; -- &nbsp; ─</span>
        <span>SENSEX &nbsp; -- &nbsp; ─</span>
    </div>
</div>

<!-- STATUS BAR -->
<div id="status">
    <div class="st">
        <span class="st-lbl">M1 FII</span>
        <span style="color:{m1_color};font-weight:700;">{m1['verdict']}</span>
    </div>
    <div class="st">
        <span class="st-lbl">M4 MODE</span>
        <span style="color:{m4_color};font-weight:700;">{m4['risk_mode']}</span>
    </div>
    <div class="st">
        <span class="st-lbl">M7 RISK</span>
        <span style="color:{m7_color};font-weight:700;">{m7['risk_level']}</span>
    </div>
    <div class="st">
        <span class="st-lbl">A/D</span>
        <span style="color:#888;">{m4.get('advances',0):,} / {m4.get('declines',0):,}</span>
    </div>
    <div class="st">
        <span class="st-lbl">BAN</span>
        <span style="color:{m7_color};">{m7['ban_count']} stocks</span>
    </div>
    <div class="st" style="margin-left:auto;color:#1a1a1a;">NSE DATA · {TODAY_STR}</div>
</div>

<!-- THREE COMBINATIONS -->
<div id="main">
    {m1_html}
    {m4_html}
    {m7_html}
</div>

<div id="footer">
    <span>QUANTIS MARKET INTELLIGENCE · M1 + M4 + M7 · NSE INDIA</span>
    <span>For informational purposes only · Not investment advice</span>
</div>

</body>
</html>'''

# ================================================================
#  MAIN
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*55)
    print(f"  QUANTIS — MARKET INTELLIGENCE")
    print(f"  M1 + M4 + M7  |  {TODAY_STR}")
    print("="*55)

    m1 = process_m1()
    m4 = process_m4()
    m7 = process_m7()

    html = build_html(m1, m4, m7)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    combined = {'m1': m1, 'm4': m4, 'm7': m7, 'date': TODAY_STR}
    with open('market_data.json', 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    print(f"\n{'='*55}")
    print(f"  market.html ready! Open in browser.")
    print(f"  market_data.json saved!")
    print(f"{'='*55}")
    print(f"""
  FILES NEEDED IN market-data/:
  ─────────────────────────────────────────────
  DAILY (roz download karo from NSE):
  daily/fii-dii-combined-latest.csv
    → nseindia.com/market-data/fii-dii-activity
    → "Download (.csv)" button

  daily/fii_stats_[date].xls
    → nseindia.com/all-reports (Derivatives section)
    → "FII Derivatives Statistics" → Download XLS

  daily/bhavcopy_csv.csv
    → nseindia.com/all-reports (Equity section)
    → "Bhavcopy" CSV download

  WEEKLY (har hafte update karo):
  weekly/fao_participant_oi_[date].csv
    → nseindia.com/all-reports (Derivatives)
    → "Participant wise Open Interest" → Download

  weekly/fo_ban_csv.csv
    → nseindia.com/all-reports (Derivatives)
    → "Securities in F&O Ban" → Download
  ─────────────────────────────────────────────
""")