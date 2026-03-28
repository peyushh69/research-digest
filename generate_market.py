# ================================================================
#  QUANTIS — generate_market.py  (FINAL VERSION)
#  M1: Smart Money Divergence
#  M4: Sector Rotation Map
#  M7: Leverage & Risk Meter
#
#  Run: python generate_market.py
#  Output: market.html
#
#  market-data/ folder structure:
#  ├── daily/
#  │   ├── fii-dii-combined-latest.csv   ← NSE FII/DII cash
#  │   ├── fii_stats_[date].xls          ← NSE FII derivatives
#  │   └── bhavcopy_csv.csv              ← NSE EOD bhavcopy
#  └── weekly/
#      ├── fao_participant_oi_[date].csv ← NSE participant OI
#      └── fo_ban_csv.csv               ← NSE F&O ban list
# ================================================================

import os, glob, csv, json, re, sys
from datetime import datetime

# Configure stdout to handle UTF-8 characters on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATA_FOLDER = "market-data"
OUTPUT_FILE = "market.html"
TODAY_STR   = datetime.today().strftime('%d %b %Y').upper()

os.makedirs(os.path.join(DATA_FOLDER, "daily"),   exist_ok=True)
os.makedirs(os.path.join(DATA_FOLDER, "weekly"),  exist_ok=True)
os.makedirs(os.path.join(DATA_FOLDER, "monthly"), exist_ok=True)

# ================================================================
#  UTILITIES
# ================================================================

def find(subfolder, patterns):
    base = os.path.join(DATA_FOLDER, subfolder)
    for p in patterns:
        files = glob.glob(os.path.join(base, p))
        if files:
            return sorted(files)[-1]
    return None

def clean_key(k):
    return str(k).strip().replace('\n','').replace('\r','').replace('  ',' ')

def read_csv(fp):
    import io
    for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
        try:
            with open(fp, 'r', encoding=enc) as f:
                content = f.read()
            if not content:
                continue
            
            reader = csv.reader(io.StringIO(content))
            raw_rows = list(reader)
            if not raw_rows:
                continue

            header_idx = 0
            for i, row in enumerate(raw_rows):
                if not row:
                    continue
                first_cell = row[0].strip()
                if first_cell and len(first_cell) < 40 and 'chr(0)' not in first_cell:
                    if len(row) > 2:
                        header_idx = i
                        break
            
            headers = [clean_key(k) for k in raw_rows[header_idx]]
            rows = []
            for row in raw_rows[header_idx+1:]:
                if not any(row): continue
                # Zip with padding
                padded = row + [''] * max(0, len(headers) - len(row))
                rows.append(dict(zip(headers, padded[:len(headers)])))
            
            if rows:
                return rows
        except:
            continue
    return []

def parse_html_table(html):
    rows    = []
    headers = []
    tr_pat  = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL|re.IGNORECASE)
    td_pat  = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL|re.IGNORECASE)
    tag_pat = re.compile(r'<[^>]+>')
    for i, tr in enumerate(tr_pat.finditer(html)):
        cells = [tag_pat.sub('', td.group(1)).strip()
                 for td in td_pat.finditer(tr.group(1))]
        if not cells or not any(cells):
            continue
        if i == 0 or not headers:
            headers = cells
        else:
            padded = (cells + [''] * len(headers))[:len(headers)]
            rows.append(dict(zip(headers, padded)))
    return rows

def read_xls(fp):
    # Try 1: NSE exports HTML disguised as XLS
    try:
        with open(fp, 'rb') as f:
            raw = f.read()
        if b'<html' in raw[:500].lower() or b'<table' in raw[:1000].lower():
            content = raw.decode('utf-8-sig', errors='ignore')
            rows = parse_html_table(content)
            if rows:
                print(f"  XLS read as HTML: {len(rows)} rows")
                return rows
    except Exception as e:
        pass

    # Try 2: xlrd (XLS)
    try:
        import xlrd
        wb = xlrd.open_workbook(fp)
        ws = wb.sheet_by_index(0)
        
        # 1. Capture ALL data from the sheet into a simple list of lists first
        all_sheet_data = []
        for r in range(ws.nrows):
            all_sheet_data.append([str(ws.cell_value(r, c)).strip() for c in range(ws.ncols)])

        # 2. Find the best header row (the one with keywords)
        best_row_idx = 0
        keywords = ['INSTRUMENT', 'BUY', 'SELL', 'INDEX', 'STOCK', 'VALUE']
        for i, row_vals in enumerate(all_sheet_data[:15]):
            row_str = ' '.join(row_vals).upper()
            if any(k in row_str for k in keywords) and sum(1 for v in row_vals if len(v) > 0) > 3:
                best_row_idx = i
                break

        headers = []
        for i, h in enumerate(all_sheet_data[best_row_idx]):
            if not h or h.strip() == "":
                headers.append(f"Col{i}")
            else:
                hdr = h.strip().upper()
                # If duplicate header, add index
                if hdr in headers:
                    headers.append(f"{hdr}_{i}")
                else:
                    headers.append(hdr)
        
        rows = []
        for row_vals in all_sheet_data[best_row_idx + 1:]:
            if any(v for v in row_vals if len(v) > 0):
                rows.append(dict(zip(headers, row_vals)))
        
        if rows:
            print(f"  XLS (xlrd) processed: {len(rows)} rows. Header: {headers[:10]}")
            return rows
    except ImportError: pass
    except Exception as e: print(f"  xlrd error: {e}")

    # Try 3: openpyxl (XLSX)
    try:
        import openpyxl
        wb = openpyxl.load_workbook(fp, data_only=True)
        ws = wb.active
        # Same logic for openpyxl
        all_data = list(ws.values)
        best_row_idx = 0
        max_filled = 0
        for i, row in enumerate(all_data[:15]):
            if not row: continue
            row_str = [str(v).strip() if v else "" for v in row]
            filled = sum(1 for v in row_str if len(v) > 2)
            if any(k in ' '.join(row_str).upper() for k in ['INSTRUMENT', 'BUY', 'SELL', 'DATE']):
                filled += 10
            if filled > max_filled:
                max_filled = filled
                best_row_idx = i

        headers = [str(h).replace('\n',' ').strip() if h else f"Col{j}" for j,h in enumerate(all_data[best_row_idx])]
        rows = []
        for row in all_data[best_row_idx+1:]:
            if any(row):
                rows.append(dict(zip(headers, [str(v).strip() if v else "" for v in row])))
        if rows:
            print(f"  XLSX (openpyxl) loaded from row {best_row_idx}")
            return rows
    except Exception as e:
        print(f"  openpyxl error: {e}")

    # Try reading as text/CSV (some NSE XLS are tab-separated text)
    try:
        for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
            try:
                with open(fp, 'r', encoding=enc) as f:
                    content_txt = f.read()
                if len(content_txt) > 10:
                    # Tab separated?
                    if '\t' in content_txt:
                        lines = content_txt.strip().split('\n')
                        hdrs  = [h.strip() for h in lines[0].split('\t')]
                        rows  = []
                        for line in lines[1:]:
                            vals = [v.strip() for v in line.split('\t')]
                            if any(vals):
                                rows.append(dict(zip(hdrs, vals + ['']*(len(hdrs)-len(vals)))))
                        if rows:
                            print(f"  XLS read as TSV: {len(rows)} rows")
                            return rows
            except:
                continue
    except Exception as e:
        pass
    print(f"  Cannot read XLS — Run: pip install xlrd")
    print(f"  Alternative: Open fii_stats.xls in Excel → Save As → CSV")
    print(f"  Then rename to fii_stats.csv in market-data/daily/")
    return []

def num(val):
    try:
        v = str(val).replace(',','').replace('(', '-').replace(')','') \
                    .replace('₹','').replace('%','').strip()
        return float(v) if v and v not in ['-',''] else 0.0
    except:
        return 0.0

def fc(v): return '#00cc44' if v > 0 else ('#ff3333' if v < 0 else '#888888')
def cr(v): return f"{'+'if v>=0 else ''}₹{abs(v):,.0f} Cr"

# ================================================================
#  M1: SMART MONEY DIVERGENCE
# ================================================================

def process_m1():
    print("\n" + "─"*50)
    print("[M1] Smart Money Divergence")
    print("─"*50)

    result = {
        'cash':       {'buy':0,'sell':0,'net':0},
        'dii_cash':   {'buy':0,'sell':0,'net':0},
        'index_fut':  {'long':0,'short':0,'net':0},
        'stock_fut':  {'long':0,'short':0,'net':0},
        'index_opt':  {'net':0},
        'stock_opt':  {'net':0},
        'date':       TODAY_STR,
        'verdict':    'NO DATA',
        'verdict_col':'#888888',
        'verdict_detail': 'Add fii-dii-combined-latest.csv to market-data/daily/',
        'risk':       'UNKNOWN',
        'cash_dir':   'NO DATA',
        'fut_dir':    'NO DATA',
        'total_net':  0,
    }

    # FII/DII Cash CSV
    # Columns: CATEGORY | DATE | BUY VALUE (₹ Crores) | SELL VALUE | NET VALUE
    cash_file = find('daily', [
        'fii-dii-combined-latest.csv','fii-dii*.csv',
        'fii_dii*.csv','FII_DII*.csv','FII*.csv'
    ])
    if cash_file:
        rows = read_csv(cash_file)
        print(f"  Cash: {os.path.basename(cash_file)}")
        for row in rows:
            cat_key  = next((k for k in row if 'CATEGORY' in k.upper()), None)
            buy_key  = next((k for k in row if 'BUY' in k.upper()), None)
            sell_key = next((k for k in row if 'SELL' in k.upper()), None)
            net_key  = next((k for k in row if 'NET' in k.upper()), None)
            date_key = next((k for k in row if 'DATE' in k.upper()), None)
            if not cat_key:
                continue
            cat  = row[cat_key].strip().strip('"').upper()
            buy  = num(row.get(buy_key, 0))
            sell = num(row.get(sell_key, 0))
            net  = num(row.get(net_key, buy - sell))
            if date_key and row[date_key]:
                result['date'] = row[date_key].strip('"').upper()
            if 'FII' in cat or 'FPI' in cat:
                result['cash'] = {'buy':buy,'sell':sell,'net':net}
                print(f"  FII Cash  Buy:{buy:>10,.0f}  Sell:{sell:>10,.0f}  Net:{net:>+11,.0f}")
            elif 'DII' in cat:
                result['dii_cash'] = {'buy':buy,'sell':sell,'net':net}
                print(f"  DII Cash  Buy:{buy:>10,.0f}  Sell:{sell:>10,.0f}  Net:{net:>+11,.0f}")
    else:
        print("  ✗ fii-dii-combined-latest.csv not found")

    # FII Stats XLS (derivatives)
    deriv_file = find('daily', [
        'fii_stats*.xls','fii_stats*.xlsx','fii_stats*.csv',
        'fii-stats*.xls','FII*stat*.xls','FII*deriv*.xls','fii*.xls'
    ])
    if deriv_file:
        ext  = os.path.splitext(deriv_file)[1].lower()
        rows = read_xls(deriv_file) if ext in ['.xls','.xlsx'] else read_csv(deriv_file)
        if rows:
            print(f"  Derivatives: {os.path.basename(deriv_file)}")
            # Debug: what headers did we get?
            actual_hdrs = list(rows[0].keys())
            print(f"  Headers Found: {actual_hdrs[:10]}")

        print(f"  --- DEBUG: FIRST 5 ROWS DATA ---")
        for i, row in enumerate(rows[:5]):
            print(f"  Row {i}: {list(row.values())}")
        print(f"  --------------------------------")

        for row in rows:
            keys = list(row.keys())
            if not keys: continue
            
            # 1. Instrument (Instrument is always in Column 0, now 'Col0')
            inst = str(row.get('Col0', row.get(keys[0], ''))).upper().strip()
            
            # 2. Extract Data (Index 2 is always Buy Value, Index 4 is always Sell Value)
            # We try unique headers first (BUY_2, SELL_4) else fallback to indexes
            buy_val  = num(row.get('BUY_2', num(row.get(keys[min(2, len(keys)-1)], 0))))
            sell_val = num(row.get('SELL_4', num(row.get(keys[min(4, len(keys)-1)], 0))))
            net = buy_val - sell_val

            # Flexible matching for NSE labels
            if any(x in inst for x in ['INDEX FUTURES','INDEX FUT','FUTIDX','IDXFUT']):
                result['index_fut'] = {'long':buy_val,'short':sell_val,'net':net}
                print(f"  Idx Fut   Long:{buy_val:>10,.0f}  Short:{sell_val:>10,.0f}  Net:{net:>+11,.0f}")
            elif any(x in inst for x in ['STOCK FUTURES','STOCK FUT','FUTSTK','STKFUT']):
                result['stock_fut'] = {'long':buy_val,'short':sell_val,'net':net}
                print(f"  Stk Fut   Long:{buy_val:>10,.0f}  Short:{sell_val:>10,.0f}  Net:{net:>+11,.0f}")
            elif any(x in inst for x in ['INDEX OPTIONS','INDEX OPT','OPTIDX','IDXOPT']):
                result['index_opt'] = {'net':net}
            elif any(x in inst for x in ['STOCK OPTIONS','STOCK OPT','OPTSTK','STKOPT']):
                result['stock_opt'] = {'net':net}
    else:
        print("  ✗ fii_stats.xls not found")

    # Verdict
    cash_net = result['cash']['net']
    fut_net  = result['index_fut']['net'] + result['stock_fut']['net']
    cash_dir = 'BUY' if cash_net >= 0 else 'SELL'
    has_fut  = result['index_fut']['long'] != 0 or result['index_fut']['short'] != 0
    fut_dir  = ('LONG' if fut_net >= 0 else 'SHORT') if has_fut else 'NO DATA'

    combos = {
        ('SELL','LONG'):  ('HEDGE',               '#4488ff','LOW',
                           'Cash sell lekin futures LONG — FII hedge kar raha hai, exit nahi. Oct 2021 wala pattern.'),
        ('SELL','SHORT'): ('REAL EXIT',            '#ff3333','HIGH',
                           'Cash sell + futures SHORT — Genuine bearish exit. Avoid fresh longs.'),
        ('BUY', 'LONG'):  ('AGGRESSIVE ACCUMULATE','#00cc44','VERY LOW',
                           'Cash buy + futures LONG — Strong bullish conviction. FII accumulating hard.'),
        ('BUY', 'SHORT'): ('PROFIT BOOKING',       '#ff9944','MEDIUM',
                           'Cash buy lekin futures SHORT — Profits book kar raha hai ya longs hedge.'),
        ('SELL','NO DATA'):('SELLING',             '#ff6600','MEDIUM',
                            'FII cash sell kar raha hai. Add fii_stats.xls for complete picture.'),
        ('BUY', 'NO DATA'):('BUYING',              '#00cc44','LOW',
                            'FII cash buy kar raha hai. Add fii_stats.xls for complete picture.'),
    }
    v, vc, risk, detail = combos.get(
        (cash_dir, fut_dir),
        ('NEUTRAL','#888888','NEUTRAL','No clear FII directional bias today.'))

    result.update({
        'verdict':v,'verdict_col':vc,'verdict_detail':detail,
        'risk':risk,'cash_dir':cash_dir,'fut_dir':fut_dir,
        'total_net': cash_net + fut_net + result['index_opt']['net'],
    })
    print(f"\n  VERDICT: {v} | Cash:{cash_dir} | Fut:{fut_dir} | Risk:{risk}")
    return result

# ================================================================
#  M4: SECTOR ROTATION MAP
# ================================================================

SECTORS = {
    'IT':      ['TCS','INFY','WIPRO','HCLTECH','TECHM','LTIM','MPHASIS','PERSISTENT'],
    'BANKING': ['HDFCBANK','ICICIBANK','KOTAKBANK','SBIN','AXISBANK','INDUSINDBK','BANDHANBNK'],
    'AUTO':    ['MARUTI','TATAMOTORS','BAJAJ-AUTO','HEROMOTOCO','EICHERMOT','M&M','TVSMOTOR'],
    'PHARMA':  ['SUNPHARMA','DRREDDY','CIPLA','DIVISLAB','APOLLOHOSP','AUROPHARMA'],
    'METALS':  ['TATASTEEL','JSWSTEEL','HINDALCO','VEDL','COALINDIA','SAIL','NMDC'],
    'ENERGY':  ['RELIANCE','ONGC','NTPC','POWERGRID','BPCL','IOC','TATAPOWER','ADANIGREEN'],
    'FMCG':    ['HINDUNILVR','ITC','NESTLEIND','BRITANNIA','DABUR','GODREJCP','MARICO'],
    'FINANCE': ['BAJFINANCE','BAJAJFINSV','SBILIFE','HDFCLIFE','ICICIPRULI','CHOLAFIN'],
    'INFRA':   ['LT','ADANIENT','ADANIPORTS','DLF','ULTRACEMCO','GRASIM'],
    'TELECOM': ['BHARTIARTL','IDEA','INDUSTOWER'],
}

# ================================================================
#  M2: PUT-CALL RATIO / OPTIONS SENTIMENT
# ================================================================

def process_m2():
    print("\n" + "─"*50)
    print("[M2] Options Sentiment — PCR")
    print("─"*50)

    result = {
        'pcr': 0.0, 'pcr_signal': 'NO DATA', 'pcr_col': '#888888',
        'nifty_put_oi': 0, 'nifty_call_oi': 0,
        'top_put_strike': 0, 'top_call_strike': 0,
        'signal': 'NO DATA', 'signal_col': '#888888', 'date': TODAY_STR,
        'detail': 'Add fo_participant_combined.csv or options_chain.csv'
    }

    # Try participant OI file — contains Put & Call OI columns
    oi_file = find('weekly', [
        'fao_participant_oi*.csv', 'participant_oi*.csv', '*participant*oi*.csv'
    ])
    if oi_file:
        rows = read_csv(oi_file)
        total_call_oi = total_put_oi = 0
        for r in rows:
            # Sum all client types for PUTS and CALLS
            for k, v in r.items():
                ku = k.upper()
                val = num(v)
                if 'OPTION' in ku and 'CALL' in ku and 'LONG' in ku:  total_call_oi += val
                if 'OPTION' in ku and 'PUT'  in ku and 'LONG' in ku:  total_put_oi  += val

        if total_call_oi > 0:
            pcr = round(total_put_oi / total_call_oi, 2)
            result['nifty_put_oi']  = total_put_oi
            result['nifty_call_oi'] = total_call_oi
            result['pcr'] = pcr

            if pcr >= 1.3:
                result.update({'pcr_signal': 'EXTREME FEAR', 'pcr_col': '#22c55e',
                               'signal': 'EXTREME FEAR', 'signal_col': '#22c55e',
                               'detail': f'PCR {pcr} — Heavy put buying = contrarian bullish signal'})
            elif pcr >= 1.0:
                result.update({'pcr_signal': 'BEARISH BIAS', 'pcr_col': '#f97316',
                               'signal': 'BEARISH BIAS', 'signal_col': '#f97316',
                               'detail': f'PCR {pcr} — Put dominance. Market cautious / hedged.'})
            elif pcr >= 0.7:
                result.update({'pcr_signal': 'NEUTRAL', 'pcr_col': '#888888',
                               'signal': 'NEUTRAL', 'signal_col': '#888888',
                               'detail': f'PCR {pcr} — Balanced put-call positioning.'})
            else:
                result.update({'pcr_signal': 'EXTREME GREED', 'pcr_col': '#ef4444',
                               'signal': 'EXTREME GREED', 'signal_col': '#ef4444',
                               'detail': f'PCR {pcr} — Heavy call writing = contrarian bearish signal'})
            print(f"  PCR: {pcr} | Signal: {result['pcr_signal']}")
        else:
            # Try finding Put/Call OI columns differently
            print("  OI file found but Put/Call columns not detected")
    else:
        print("  ✗ Participant OI file not found — PCR unavailable")

    return result

# ================================================================
#  M3: NIFTY TREND + FAIR VALUE SIGNAL
# ================================================================

def process_m3():
    print("\n" + "─"*50)
    print("[M3] Nifty Trend + Fair Value")
    print("─"*50)

    result = {
        'nifty_close': 0.0, 'nifty_prev': 0.0, 'nifty_chg': 0.0, 'nifty_chg_pct': 0.0,
        'nifty_high': 0.0, 'nifty_low': 0.0, 'nifty_open': 0.0,
        'banknifty_close': 0.0, 'banknifty_chg_pct': 0.0,
        'nifty_midcap_close': 0.0, 'nifty_midcap_chg_pct': 0.0,
        'nifty_smallcap_close': 0.0,
        'vix_close': 0.0, 'vix_signal': 'NO DATA', 'vix_col': '#888888',
        'trend': 'NO DATA', 'trend_col': '#888888',
        'signal': 'NO DATA', 'signal_col': '#888888', 'date': TODAY_STR,
        'detail': 'Add bhavcopy_csv.csv (index series) to market-data/daily/',
    }

    # Look in bhavcopy for index data - NSE index bhavcopy has different columns
    idx_file = find('daily', [
        'ind_close_all*.csv', 'ind_nifty*.csv', 'Indices*.csv',
        'bhavcopy_csv.csv', 'NIFTY*.csv', 'bhavcopy*.csv'
    ])
    if not idx_file:
        print("  ✗ No bhavcopy/index file found")
        return result

    rows = read_csv(idx_file)
    print(f"  Index file: {os.path.basename(idx_file)} ({len(rows)} rows)")
    if rows:
        print(f"  Columns sample: {list(rows[0].keys())[:6]}")

    # Try to extract NIFTY 50, BANK NIFTY, INDIA VIX from bhavcopy
    for r in rows:
        sym = str(r.get('SYMBOL', r.get('Symbol', r.get('INDEX_NAME', r.get('Name', ''))))).upper().strip()
        try:
            close = num(r.get('CLOSE', r.get('CLOSE_PRICE', r.get('Close', r.get('ClosingIndex', 0)))))
            prev  = num(r.get('PREV_CLOSE', r.get('PREVCLOSE', r.get('PrevClose', r.get('PreviousClose', 0)))))
            high  = num(r.get('HIGH', r.get('HIGH_PRICE', r.get('High', 0))))
            low   = num(r.get('LOW', r.get('LOW_PRICE', r.get('Low', 0))))
            open_ = num(r.get('OPEN', r.get('OPEN_PRICE', r.get('Open', 0))))

            if close > 0:
                chg_pct = round((close - prev) / prev * 100, 2) if prev > 0 else 0.0

            if any(x in sym for x in ['NIFTY 50', 'NIFTY50']) and 'BANK' not in sym and 'MID' not in sym:
                result.update({
                    'nifty_close': close, 'nifty_prev': prev,
                    'nifty_high': high, 'nifty_low': low, 'nifty_open': open_,
                    'nifty_chg': round(close - prev, 2) if prev > 0 else 0,
                    'nifty_chg_pct': chg_pct,
                })
                print(f"  NIFTY 50: {close:,.2f} ({chg_pct:+.2f}%)")
            elif 'BANK NIFTY' in sym or 'BANKNIFTY' in sym:
                result.update({'banknifty_close': close, 'banknifty_chg_pct': chg_pct})
            elif 'MIDCAP' in sym and '100' in sym:
                result.update({'nifty_midcap_close': close, 'nifty_midcap_chg_pct': chg_pct})
            elif 'SMALLCAP' in sym:
                result['nifty_smallcap_close'] = close
            elif 'VIX' in sym or 'INDIA VIX' in sym:
                result['vix_close'] = close
                if close >= 25:
                    result.update({'vix_signal': 'HIGH FEAR', 'vix_col': '#ef4444'})
                elif close >= 18:
                    result.update({'vix_signal': 'ELEVATED', 'vix_col': '#f97316'})
                elif close >= 12:
                    result.update({'vix_signal': 'NORMAL', 'vix_col': '#22c55e'})
                else:
                    result.update({'vix_signal': 'LOW — COMPLACENT', 'vix_col': '#888888'})
                print(f"  VIX: {close:.2f} → {result['vix_signal']}")
        except:
            continue

    # Determine trend from NIFTY performance
    chg = result['nifty_chg_pct']
    if chg >= 1.0:
        result.update({'trend': 'STRONG UPTREND', 'trend_col': '#22c55e',
                       'signal': 'STRONG UPTREND', 'signal_col': '#22c55e',
                       'detail': f'Nifty +{chg:.2f}% — Broad strength. Ride the trend.'})
    elif chg >= 0.2:
        result.update({'trend': 'MILD UPTREND', 'trend_col': '#22c55e',
                       'signal': 'MILD UPTREND', 'signal_col': '#22c55e',
                       'detail': f'Nifty +{chg:.2f}% — Slight positive bias.'})
    elif chg <= -1.0:
        result.update({'trend': 'STRONG DOWNTREND', 'trend_col': '#ef4444',
                       'signal': 'STRONG DOWNTREND', 'signal_col': '#ef4444',
                       'detail': f'Nifty {chg:.2f}% — Broad weakness. Defensive mode.'})
    elif chg <= -0.2:
        result.update({'trend': 'MILD DOWNTREND', 'trend_col': '#f97316',
                       'signal': 'MILD DOWNTREND', 'signal_col': '#f97316',
                       'detail': f'Nifty {chg:.2f}% — Slight negative bias. Caution.'})
    elif result['nifty_close'] > 0:
        result.update({'trend': 'SIDEWAYS', 'trend_col': '#888888',
                       'signal': 'SIDEWAYS', 'signal_col': '#888888',
                       'detail': f'Nifty {chg:.2f}% — Range-bound. Avoid directional bets.'})

    print(f"  TREND: {result['trend']} | VIX: {result['vix_close']:.2f}")
    return result


def process_m4():
    print("\n" + "─"*50)
    print("[M4] Sector Rotation Map")
    print("─"*50)

    result = {
        'sectors':{},'top_3':[],'bottom_3':[],
        'risk_mode':'NO DATA',
        'signal':'Add bhavcopy_csv.csv to market-data/daily/',
        'signal_col':'#888888',
        'advances':0,'declines':0,'unchanged':0,
        'avg_delivery':0,'date':TODAY_STR,
    }

    # Bhavcopy: SYMBOL,SERIES,DATE1,PREV_CLOSE,OPEN_PRICE,HIGH_PRICE,
    #           LOW_PRICE,LAST_PRICE,CLOSE_PRICE,AVG_PRICE,TTL_TRD_QNTY,
    #           TURNOVER_LACS,NO_OF_TRADES,DELIV_QTY,DELIV_PER
    bhav = find('daily',[
        'bhavcopy_csv.csv','bhavcopy*.csv',
        'cm*bhav.csv','NSE_CM*.csv','EQUITY*.csv','eq*.csv'
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
        sym    = str(row.get('SYMBOL', row.get('Symbol',''))).strip()
        series = str(row.get('SERIES', row.get('Series',''))).strip()
        if series not in ['EQ','BE']:
            continue
        try:
            close = num(row.get('CLOSE_PRICE', row.get('CLOSE', row.get('Close Price',0))))
            prev  = num(row.get('PREV_CLOSE',  row.get('PREVCLOSE', row.get('Prev Close',0))))
            deliv = num(row.get('DELIV_PER',   row.get('DELIVERY_PER',
                        row.get('% Dly Qt to Traded Qt', 0))))
            if close > 0 and prev > 0:
                pct = round(((close - prev) / prev) * 100, 2)
                stock_perf[sym] = pct
                if   pct >  0.05: adv  += 1
                elif pct < -0.05: dec  += 1
                else:             unch += 1
                if deliv > 0:
                    deliveries.append(deliv)
        except:
            continue

    result.update({
        'advances':adv,'declines':dec,'unchanged':unch,
        'avg_delivery': round(sum(deliveries)/len(deliveries),1) if deliveries else 0
    })

    sector_perf = {}
    for sector, stocks in SECTORS.items():
        vals = [stock_perf[s] for s in stocks if s in stock_perf]
        if vals:
            sector_perf[sector] = round(sum(vals)/len(vals), 2)
            print(f"  {sector:10}: {sector_perf[sector]:+.2f}%  ({len(vals)}/{len(stocks)})")

    result['sectors'] = sector_perf
    if sector_perf:
        ranked = sorted(sector_perf.items(), key=lambda x:x[1], reverse=True)
        result['top_3']    = ranked[:3]
        result['bottom_3'] = ranked[-3:][::-1]
        def_s = sum(sector_perf.get(s,0) for s in ['PHARMA','IT','FMCG'])
        cyc_s = sum(sector_perf.get(s,0) for s in ['AUTO','METALS','ENERGY','BANKING'])
        if   cyc_s > def_s + 1:
            result.update({'risk_mode':'RISK-ON', 'signal_col':'#00cc44',
                           'signal':'Cyclicals outperforming — RISK-ON mode active'})
        elif def_s > cyc_s + 1:
            result.update({'risk_mode':'RISK-OFF','signal_col':'#4488ff',
                           'signal':'Defensives outperforming — RISK-OFF mode active'})
        else:
            result.update({'risk_mode':'MIXED',   'signal_col':'#888888',
                           'signal':'No clear sector rotation — mixed market'})

    print(f"\n  MODE: {result['risk_mode']} | A:{adv} D:{dec} | Del:{result['avg_delivery']}%")
    return result

# ================================================================
#  M7: LEVERAGE & RISK METER
# ================================================================

def process_m7():
    print("\n" + "─"*50)
    print("[M7] Leverage & Risk Meter")
    print("─"*50)

    result = {
        'ban_count':0,'ban_stocks':[],'ban_date':'',
        'fii_idx_long':0,'fii_idx_short':0,
        'fii_stk_long':0,'fii_stk_short':0,
        'fii_ls_ratio':0,'fii_signal':'NO DATA',
        'risk_level':'UNKNOWN','risk_col':'#888888',
        'risk_detail':'Add fo_ban_csv.csv to market-data/weekly/',
        'date':TODAY_STR,
    }

    # Ban list: "Securities in Ban For Trade Date DD-MMM-YYYY:\n1,SAIL"
    ban_file = find('weekly',[
        'fo_ban_csv.csv','fo_ban*.csv','ban*.csv','*ban*list*.csv'
    ])
    if ban_file:
        ban_stocks = []
        ban_date   = ''
        with open(ban_file,'r',encoding='utf-8-sig',errors='ignore') as f:
            for line in f:
                line = line.strip().strip('"')
                if not line:
                    continue
                if 'Securities in Ban' in line or 'Ban For Trade' in line:
                    m = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', line)
                    if m:
                        ban_date = m.group(1).upper()
                    continue
                parts = [p.strip().strip('"') for p in line.split(',')]
                sym   = parts[-1] if len(parts) >= 2 else parts[0]
                sym   = sym.strip().upper()
                if sym and not sym.isdigit() and len(sym)>1 and sym not in ['SYMBOL','SECURITY','SR.NO']:
                    ban_stocks.append(sym)
        result['ban_count']  = len(ban_stocks)
        result['ban_stocks'] = ban_stocks
        result['ban_date']   = ban_date
        print(f"  Ban ({ban_date}): {len(ban_stocks)} — {', '.join(ban_stocks[:12])}")
    else:
        print("  ✗ fo_ban_csv.csv not found")

    # Participant OI
    # Confirmed columns: Client Type | Future Index Long | Future Index Short |
    #                    Future Stock Long | Future Stock Short | ...
    oi_file = find('weekly',[
        'fao_participant_oi*.csv','participant_oi*.csv',
        'Participant_OI*.csv','*participant*oi*.csv'
    ])
    if oi_file:
        # NSE OI file has title row as first line — skip it
        raw_rows = read_csv(oi_file)
        # Filter: real data rows have 'Client Type' as first column key
        # or skip rows where first key contains 'Participant wise'
        rows = []
        for r in raw_rows:
            first_key = list(r.keys())[0] if r else ''
            first_val = list(r.values())[0] if r else ''
            # Skip title rows (keys look like title text or values are empty)
            if 'Participant wise' in first_key or 'Participant wise' in first_val:
                continue
            if not any(r.values()):
                continue
            rows.append(r)
        print(f"  Participant OI: {os.path.basename(oi_file)} ({len(rows)} data rows)")
        if rows:
            print(f"  Columns: {list(rows[0].keys())[:5]}")

        fii_il = fii_is = fii_sl = fii_ss = 0
        for row in rows:
            cat_key = next((k for k in row
                           if 'CLIENT' in k.upper() or 'TYPE' in k.upper()
                           or k.strip().upper()=='CATEGORY'), list(row.keys())[0])
            cat = str(row.get(cat_key,'')).upper().strip().strip('"')
            if not ('FII' in cat or 'FPI' in cat):
                continue

            # Try exact confirmed column names first
            il = num(row.get('Future Index Long',
                     row.get('FUTURE INDEX LONG',
                     row.get('Fut Idx Long',0))))
            is_= num(row.get('Future Index Short',
                     row.get('FUTURE INDEX SHORT',
                     row.get('Fut Idx Short',0))))
            sl = num(row.get('Future Stock Long',
                     row.get('FUTURE STOCK LONG',
                     row.get('Fut Stk Long',0))))
            ss = num(row.get('Future Stock Short',
                     row.get('FUTURE STOCK SHORT',
                     row.get('Fut Stk Short',0))))

            # Fallback: scan columns by keyword
            if il == 0 and is_ == 0:
                for k, v in row.items():
                    ku = k.upper()
                    if 'INDEX' in ku and 'LONG' in ku   and 'FUT' in ku: il  = num(v)
                    if 'INDEX' in ku and 'SHORT' in ku  and 'FUT' in ku: is_ = num(v)
                    if 'STOCK' in ku and 'LONG' in ku   and 'FUT' in ku: sl  = num(v)
                    if 'STOCK' in ku and 'SHORT' in ku  and 'FUT' in ku: ss  = num(v)

            fii_il, fii_is, fii_sl, fii_ss = il, is_, sl, ss
            print(f"  FII OI  IdxL:{il:,.0f}  IdxS:{is_:,.0f}  StkL:{sl:,.0f}  StkS:{ss:,.0f}")

        result.update({
            'fii_idx_long':fii_il,'fii_idx_short':fii_is,
            'fii_stk_long':fii_sl,'fii_stk_short':fii_ss,
        })
        total_l = fii_il + fii_sl
        total_s = fii_is + fii_ss
        if total_s > 0:
            ratio = round(total_l / total_s, 2)
            result['fii_ls_ratio'] = ratio
            result['fii_signal']   = ('FII NET LONG'  if ratio > 1.3 else
                                      'FII NEUTRAL'   if ratio > 0.9 else
                                      'FII NET SHORT')
    else:
        print("  ✗ fao_participant_oi.csv not found")

    # Risk Score
    ban   = result['ban_count']
    ratio = result['fii_ls_ratio']
    score = 0
    if   ban > 15: score += 3
    elif ban > 8:  score += 2
    elif ban > 3:  score += 1
    if   ratio > 0 and ratio < 0.7: score += 3
    elif ratio > 0 and ratio < 1.0: score += 1
    elif ratio > 1.5:                score -= 1

    if   score >= 4: result.update({'risk_level':'VERY HIGH','risk_col':'#ff2222',
                     'risk_detail':f'{ban} stocks in ban + FII heavily short. Avoid leveraged positions.'})
    elif score >= 2: result.update({'risk_level':'ELEVATED', 'risk_col':'#ff9944',
                     'risk_detail':f'{ban} stocks in ban. Elevated leverage. Use smaller position sizes.'})
    elif score >= 0: result.update({'risk_level':'NORMAL',   'risk_col':'#00cc44',
                     'risk_detail':f'{ban} stocks in ban. Leverage within normal range.'})
    else:            result.update({'risk_level':'LOW',      'risk_col':'#00ff88',
                     'risk_detail':f'FII net long. Low leverage. Favorable for longs.'})

    print(f"\n  RISK: {result['risk_level']} | Ban:{ban} | L/S:{result['fii_ls_ratio']}")
    return result

# ================================================================
#  M6: INSTITUTIONAL CONVICTION METER
# ================================================================

def process_m6():
    print("\n" + "─"*50)
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
        if not cat_key or not net_key: continue
        cat = r[cat_key].strip().strip('"').upper()
        net = num(r.get(net_key, 0))
        if 'DII' in cat: dii_flows.append(net)
        if 'FII' in cat or 'FPI' in cat: fii_flows.append(net)

    dii_5d = sum(dii_flows[:5])
    fii_5d = sum(fii_flows[:5])
    result['dii_5d_net'] = dii_5d
    result['fii_5d_net'] = fii_5d

    dii_increasing = len(dii_flows) >= 2 and dii_flows[0] > dii_flows[1]

    if dii_5d > 0 and dii_increasing:
        result.update({'signal': 'Strong Conviction', 'signal_col': '#00cc44'})
    elif dii_5d > 0 and fii_5d < 0:
        result.update({'signal': 'DII Absorbing', 'signal_col': '#ff9944'})
    elif dii_5d > 0 and fii_5d > 0:
        result.update({'signal': 'Rally Support', 'signal_col': '#00ff88'})
    else:
        result.update({'signal': 'Weak Conviction', 'signal_col': '#ff3333'})

    print(f"  M6 DII 5d: {dii_5d:+.0f} | FII 5d: {fii_5d:+.0f} | Signal: {result['signal']}")
    return result

# ================================================================
#  M8: PROMOTER CONFIDENCE INDEX
# ================================================================

def process_m8():
    print("\n" + "─"*50)
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

# ================================================================
#  HTML BUILDER  (premium redesign)
# ================================================================

def build_html(m1, m2, m3, m4, m6, m7, m8):

    c   = m1['cash']
    di  = m1['dii_cash']
    fi  = m1['index_fut']
    fs  = m1['stock_fut']
    io  = m1['index_opt']

    m1c = m1['verdict_col']
    m2c = m2['signal_col']
    m3c = m3['signal_col']
    m4c = m4['signal_col']
    m6c = m6['signal_col']
    m7c = m7['risk_col']
    m8c = m8['signal_col']

    # ── M2 PCR visual bar
    pcr     = m2['pcr']
    pcr_pct = min(95, max(5, pcr / 2.0 * 100)) if pcr > 0 else 50
    pcr_col = m2['pcr_col']
    put_w   = round(m2['nifty_put_oi']  / (m2['nifty_put_oi'] + m2['nifty_call_oi'] + 1) * 100)
    call_w  = 100 - put_w

    # ── M3 index data
    nf_close  = m3['nifty_close']
    nf_chg    = m3['nifty_chg']
    nf_pct    = m3['nifty_chg_pct']
    nf_high   = m3['nifty_high']
    nf_low    = m3['nifty_low']
    bn_close  = m3['banknifty_close']
    bn_pct    = m3['banknifty_chg_pct']
    mc_close  = m3['nifty_midcap_close']
    mc_pct    = m3['nifty_midcap_chg_pct']
    vix       = m3['vix_close']
    vix_col   = m3['vix_col']
    vix_sig   = m3['vix_signal']
    vix_pct   = min(95, max(5, vix / 40 * 100)) if vix > 0 else 50
    nf_col    = '#22c55e' if nf_pct >= 0 else '#ef4444'
    bn_col    = '#22c55e' if bn_pct >= 0 else '#ef4444'
    mc_col    = '#22c55e' if mc_pct >= 0 else '#ef4444'
    nf_arr    = '▲' if nf_pct >= 0 else '▼'
    bn_arr    = '▲' if bn_pct >= 0 else '▼'
    mc_arr    = '▲' if mc_pct >= 0 else '▼'
    m3c       = m3['signal_col']

    # ── range bar (nifty day range)
    nf_range  = nf_high - nf_low if nf_high > nf_low else 1
    nf_close_w = round((nf_close - nf_low) / nf_range * 100) if nf_close > 0 and nf_range > 0 else 50


    sectors = m4.get('sectors', {})
    ranked  = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
    max_abs = max((abs(v) for _, v in ranked), default=1)
    sector_rows = ''
    for s, v in ranked:
        col = '#22c55e' if v > 0 else '#ef4444'
        pct = min(100, abs(v) / max_abs * 100)
        sign = '+' if v > 0 else ''
        arr  = '▲' if v > 0 else '▼'
        sector_rows += f'''
        <div class="sec-row">
          <span class="sec-name">{s}</span>
          <div class="sec-track"><div class="sec-fill" style="width:{pct:.0f}%;background:{col};"></div></div>
          <span class="sec-val" style="color:{col};">{arr}{sign}{v:.2f}%</span>
        </div>'''

    adv   = m4.get('advances', 0)
    dec   = m4.get('declines', 0)
    unch  = m4.get('unchanged', 0)
    total = adv + dec + unch or 1
    adv_w = round(adv / total * 100)
    del_  = m4.get('avg_delivery', 0)
    del_c = '#22c55e' if del_ >= 50 else ('#f97316' if del_ >= 35 else '#ef4444')
    ad_r  = round(adv / dec, 2) if dec > 0 else adv
    adr_c = '#22c55e' if ad_r >= 1.5 else ('#f97316' if ad_r >= 0.8 else '#ef4444')
    top3  = '  ·  '.join(f'<span style="color:#22c55e">{s}</span>&nbsp;{v:+.2f}%' for s,v in m4.get('top_3',[]))
    bot3  = '  ·  '.join(f'<span style="color:#ef4444">{s}</span>&nbsp;{v:+.2f}%' for s,v in m4.get('bottom_3',[]))

    ban_pills = ''.join(f'<span class="ban-pill">{s}</span>' for s in m7.get('ban_stocks', []))
    ratio     = m7['fii_ls_ratio']
    lsc       = '#22c55e' if ratio > 1.2 else ('#ef4444' if 0 < ratio < 0.85 else '#888')
    il  = m7['fii_idx_long'];  is_ = m7['fii_idx_short']
    sl  = m7['fii_stk_long'];  ss  = m7['fii_stk_short']

    cash_total = c['buy'] + c['sell'] or 1
    buy_w  = round(c['buy']  / cash_total * 100)

    fut_warn = '<p class="warn-note">⚠ Add fii_stats.xls for FII derivatives data</p>' if m1['fut_dir'] == 'NO DATA' else ''

    d5 = m6['dii_5d_net'];  f5 = m6['fii_5d_net']
    flow_max = max(abs(d5), abs(f5), 1)
    d5w = round(abs(d5) / flow_max * 100); d5c = '#22c55e' if d5 >= 0 else '#ef4444'
    f5w = round(abs(f5) / flow_max * 100); f5c = '#22c55e' if f5 >= 0 else '#ef4444'

    total_trades = m8['buy_count'] + m8['sell_count'] or 1
    m8buy_w  = round(m8['buy_count']  / total_trades * 100)
    m8sell_w = round(m8['sell_count'] / total_trades * 100)

    dii_row = ''
    if di.get('net', 0) != 0:
        dii_row = f'<div class="dt"><span class="dt-lbl">DII NET</span><span class="dt-val" style="color:{fc(di["net"])};">{cr(di["net"])}</span></div>'

    ratio_pct = min(95, max(5, ratio / 3 * 100)) if ratio > 0 else 50

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quantis — Market Intelligence</title>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'IBM Plex Mono', monospace; background: #000; color: #fff; padding-bottom: 60px; }}

    /* HEADER — identical to index.html */
    #site-header {{ background: #000; border-bottom: 2px solid #ff6600; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }}
    #site-logo {{ font-size: 1.6em; font-weight: 700; color: #fff; letter-spacing: 3px; }}

    /* NAV DRAWER — identical to index.html */
    #nav-drawer {{ position: fixed; top: 0; right: -260px; width: 240px; height: 100vh; background: #050505; border-left: 1px solid #1a1a1a; z-index: 999; padding: 20px 0; transition: right 0.25s ease; }}
    #nav-drawer.open {{ right: 0; }}
    #nav-drawer-header {{ display: flex; justify-content: space-between; align-items: center; padding: 0 20px 16px; border-bottom: 1px solid #1a1a1a; margin-bottom: 10px; }}
    .drawer-link {{ display: block; padding: 14px 20px; color: #555; text-decoration: none; font-size: 0.80em; font-weight: 700; letter-spacing: 3px; border-bottom: 1px solid #0f0f0f; }}
    .drawer-link:hover {{ color: #fff; background: #0a0a0a; }}
    .drawer-link.active {{ color: #ff6600; }}
    #nav-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 998; }}
    #nav-overlay.open {{ display: block; }}

    /* TICKER — identical to index.html */
    #ticker-bar {{ background: #fff; color: #000; font-size: 0.75em; font-weight: 700; padding: 5px 0; overflow: hidden; white-space: nowrap; border-bottom: 1px solid #ddd; }}
    #ticker-content {{ display: inline-block; animation: scroll-ticker 90s linear infinite; padding-left: 100%; }}
    #ticker-content span {{ margin-right: 60px; color: #000; }}
    @keyframes scroll-ticker {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}

    /* BOOKMARK PANEL — identical to index.html */
    #bookmark-panel {{ position: fixed; top: 90px; right: 20px; width: 265px; max-height: 400px; background: #0a0a0a; border: 1px solid #1a1a1a; padding: 14px; overflow-y: auto; display: none; z-index: 999; border-radius: 2px; }}
    #bookmark-panel h3 {{ color: #ff6600; letter-spacing: 3px; font-size: 0.70em; border-bottom: 1px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 10px; }}
    #bookmark-list li {{ font-size: 0.74em; color: #888; padding: 7px 0; cursor: pointer; border-bottom: 1px solid #0f0f0f; }}
    #bookmark-list li:hover {{ color: #fff; }}

    /* ═══ DASHBOARD LAYOUT ═══ */
    .page-header {{ padding: 14px 20px; border-bottom: 1px solid #111; display: flex; justify-content: space-between; align-items: center; }}
    .ph-title {{ font-size: 0.68em; font-weight: 700; color: #ff6600; letter-spacing: 3px; }}
    .ph-meta  {{ font-size: 0.60em; color: #2a2a2a; letter-spacing: 1px; }}

    #dash-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 14px 16px; max-width: 1300px; margin: 0 auto; }}
    @media (max-width: 1100px) {{ #dash-grid {{ grid-template-columns: repeat(2,1fr); }} }}
    @media (max-width: 680px)  {{ #dash-grid {{ grid-template-columns: 1fr; }} }}

    /* CARD */
    .card {{ background: #050505; border: 1px solid #151515; padding: 16px 16px 14px; display: flex; flex-direction: column; gap: 12px; }}
    .card-label {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.58em; letter-spacing: 2px; color: #2d2d2d; }}
    .card-tag {{ font-size: 0.85em; padding: 2px 6px; border: 1px solid #1a1a1a; color: #252525; letter-spacing: 1px; }}

    /* SIGNAL CHIP */
    .signal-chip {{ padding: 12px 14px; border-left: 3px solid; background: #030303; display: flex; flex-direction: column; gap: 5px; }}
    .chip-sub    {{ font-size: 0.56em; color: #2a2a2a; letter-spacing: 2px; }}
    .chip-verdict {{ font-size: 1.10em; font-weight: 700; letter-spacing: 1.5px; line-height: 1.1; }}
    .chip-detail  {{ font-size: 0.61em; color: #3a3a3a; line-height: 1.7; margin-top: 2px; }}

    /* DATA ROWS */
    .dt {{ display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #0d0d0d; }}
    .dt:last-child {{ border-bottom: none; }}
    .dt-lbl {{ font-size: 0.68em; color: #333; letter-spacing: 0.5px; }}
    .dt-val {{ font-size: 0.76em; font-weight: 700; }}

    /* BIG NUMBER */
    .big-num {{ font-size: 2.2em; font-weight: 700; line-height: 1; margin: 4px 0 2px; }}
    .big-sub  {{ font-size: 0.58em; color: #2d2d2d; letter-spacing: 1px; }}

    /* SPLIT 2-COL */
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .split-col {{ display: flex; flex-direction: column; gap: 5px; }}
    .split-title {{ font-size: 0.56em; color: #252525; letter-spacing: 2px; margin-bottom: 2px; }}

    /* BARS */
    .bar-track {{ height: 4px; background: #0f0f0f; border-radius: 2px; overflow: hidden; margin: 3px 0 5px; }}
    .bar-fill  {{ height: 100%; border-radius: 2px; }}
    .vs-bar    {{ display: flex; height: 5px; border-radius: 2px; overflow: hidden; margin: 4px 0 6px; }}
    .vs-g      {{ background: #22c55e; }}
    .vs-r      {{ background: #ef4444; flex: 1; }}

    /* SECTOR */
    .sec-row {{ display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid #090909; }}
    .sec-row:last-child {{ border-bottom: none; }}
    .sec-name  {{ font-size: 0.63em; color: #3a3a3a; width: 66px; flex-shrink: 0; }}
    .sec-track {{ flex: 1; height: 4px; background: #0f0f0f; border-radius: 2px; overflow: hidden; }}
    .sec-fill  {{ height: 100%; border-radius: 2px; }}
    .sec-val   {{ font-size: 0.66em; font-weight: 700; width: 62px; text-align: right; flex-shrink: 0; }}

    /* BAN PILL */
    .ban-pill {{ display: inline-block; padding: 3px 9px; margin: 2px; border: 1px solid #1c1c1c; color: #f97316; font-size: 0.66em; letter-spacing: 1px; }}
    .warn-note {{ font-size: 0.61em; color: #f97316; padding: 2px 0; }}

    /* RATIO TRACK */
    .ratio-track {{ position: relative; height: 5px; background: #111; border-radius: 3px; margin: 6px 0; }}
    .ratio-marker {{ position: absolute; top: -3px; width: 11px; height: 11px; border-radius: 50%; transform: translateX(-50%); }}

    /* HINT */
    .hint {{ background: #030303; padding: 10px 12px; font-size: 0.60em; color: #1f1f1f; line-height: 2; border-left: 2px solid #0f0f0f; }}

    /* FOOTER */
    #site-footer {{ padding: 10px 20px; border-top: 1px solid #0f0f0f; display: flex; justify-content: space-between; font-size: 0.57em; color: #1a1a1a; letter-spacing: 1px; margin-top: 4px; }}
    </style>
</head>
<body>

<!-- HEADER -->
<div id="site-header">
    <div id="site-logo">Quantis</div>
    <button onclick="toggleMenu()" style="background:none;border:none;cursor:pointer;color:#888;font-size:1.4em;padding:0;line-height:1;">&#9776;</button>
</div>
<div id="nav-drawer">
    <div id="nav-drawer-header">
        <span style="color:#ff6600;font-size:0.75em;letter-spacing:3px;font-weight:700;">MENU</span>
        <button onclick="toggleMenu()" style="background:none;border:none;color:#444;cursor:pointer;font-size:1.2em;">&#10005;</button>
    </div>
    <nav>
        <a href="index.html" class="drawer-link">HOME</a>
        <a href="research.html" class="drawer-link">RESEARCH</a>
        <a href="market.html" class="drawer-link active">MARKET</a>
        <a href="economy.html" class="drawer-link">ECONOMY</a>
        <a href="#" class="drawer-link" onclick="togglePanel();toggleMenu();">SAVED</a>
    </nav>
</div>
<div id="nav-overlay" onclick="toggleMenu()"></div>

<!-- TICKER -->
<div id="ticker-bar">
    <div id="ticker-content">
        <span>NIFTY 50 &nbsp; 23,114.50 &nbsp; ▲ +0.00%</span><span>SENSEX &nbsp; 74,532.96 &nbsp; ▲ +0.00%</span><span>BANK NIFTY &nbsp; 53,427.05 &nbsp; ▲ +0.00%</span><span>S&amp;P 500 &nbsp; 6,606.49 &nbsp; ▼ -0.27%</span><span>NASDAQ &nbsp; 22,090.69 &nbsp; ▼ -0.28%</span><span>DOW JONES &nbsp; 46,021.43 &nbsp; ▼ -0.44%</span><span>GOLD &nbsp; $4,657.30 &nbsp; ▲ +1.23%</span><span>CRUDE OIL &nbsp; $95.75 &nbsp; ▼ -0.41%</span><span>USD/INR &nbsp; ₹93.58 &nbsp; ▲ +0.36%</span><span>NIFTY 50 &nbsp; 23,114.50 &nbsp; ▲ +0.00%</span><span>SENSEX &nbsp; 74,532.96 &nbsp; ▲ +0.00%</span><span>BANK NIFTY &nbsp; 53,427.05 &nbsp; ▲ +0.00%</span><span>S&amp;P 500 &nbsp; 6,606.49 &nbsp; ▼ -0.27%</span><span>NASDAQ &nbsp; 22,090.69 &nbsp; ▼ -0.28%</span><span>DOW JONES &nbsp; 46,021.43 &nbsp; ▼ -0.44%</span><span>GOLD &nbsp; $4,657.30 &nbsp; ▲ +1.23%</span><span>CRUDE OIL &nbsp; $95.75 &nbsp; ▼ -0.41%</span><span>USD/INR &nbsp; ₹93.58 &nbsp; ▲ +0.36%</span>
    </div>
</div>

<!-- PAGE SUB-HEADER -->
<div class="page-header">
    <span class="ph-title">MARKET INTELLIGENCE</span>
    <span class="ph-meta">{TODAY_STR} &nbsp;·&nbsp; <span style="color:{m7c};font-weight:700;">{m7['risk_level']} RISK</span> &nbsp;·&nbsp; <span style="color:{m4c};">{m4['risk_mode']}</span></span>
</div>

<!-- DASHBOARD GRID -->
<div id="dash-grid">


<!-- M2: OPTIONS SENTIMENT -->
<div class="card">
    <div class="card-label">M2 — OPTIONS SENTIMENT <span class="card-tag">PUT-CALL RATIO</span></div>
    <div class="signal-chip" style="border-left-color:{m2c};">
        <span class="chip-sub">OPTIONS MARKET SIGNAL</span>
        <span class="chip-verdict" style="color:{m2c};">{m2['signal']}</span>
        <span class="chip-detail">{m2['detail']}</span>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:8px;">PUT / CALL OPEN INTEREST</div>
        <div class="dt"><span class="dt-lbl">TOTAL PUT OI</span><span class="dt-val" style="color:#22c55e;">{m2['nifty_put_oi']:,.0f}</span></div>
        <div class="dt"><span class="dt-lbl">TOTAL CALL OI</span><span class="dt-val" style="color:#ef4444;">{m2['nifty_call_oi']:,.0f}</span></div>
        <div class="vs-bar" style="height:7px;margin-top:6px;">
            <div class="vs-g" style="width:{put_w}%;"></div>
            <div class="vs-r"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.58em;color:#252525;margin-top:4px;">
            <span>PUT {put_w}%</span><span>CALL {call_w}%</span>
        </div>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:6px;">PCR GAUGE</div>
        <div class="big-num" style="color:{m2c};">{pcr if pcr > 0 else '─'}</div>
        <div class="big-sub">PUT-CALL RATIO</div>
        <div class="ratio-track" style="margin-top:8px;">
            <div class="ratio-marker" style="left:{pcr_pct:.0f}%;background:{m2c};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.58em;color:#1f1f1f;margin-top:4px;">
            <span>EXTREME GREED &lt;0.7</span><span>NEUTRAL 1.0</span><span>FEAR &gt;1.3</span>
        </div>
    </div>
    <div class="hint">
        PCR &gt;1.3 = extreme fear = contrarian BULLISH<br>
        PCR 0.7–1.0 = balanced / neutral market<br>
        PCR &lt;0.7 = extreme greed = contrarian BEARISH
    </div>
</div>

<!-- M3: NIFTY TREND -->
<div class="card">
    <div class="card-label">M3 — NIFTY TREND + VIX <span class="card-tag">INDEX DATA</span></div>
    <div class="signal-chip" style="border-left-color:{m3c};">
        <span class="chip-sub">INDEX TREND SIGNAL</span>
        <span class="chip-verdict" style="color:{m3c};">{m3['trend']}</span>
        <span class="chip-detail">{m3['detail']}</span>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:8px;">INDEX CLOSE PRICES</div>
        <div class="dt">
            <span class="dt-lbl">NIFTY 50</span>
            <span class="dt-val" style="color:{nf_col};">{nf_close:,.2f} &nbsp; {nf_arr}{nf_pct:+.2f}%</span>
        </div>
        <div class="dt">
            <span class="dt-lbl">BANK NIFTY</span>
            <span class="dt-val" style="color:{bn_col};">{bn_close:,.2f} &nbsp; {bn_arr}{bn_pct:+.2f}%</span>
        </div>
        <div class="dt" style="border:none;">
            <span class="dt-lbl">MIDCAP 100</span>
            <span class="dt-val" style="color:{mc_col};">{mc_close:,.2f} &nbsp; {mc_arr}{mc_pct:+.2f}%</span>
        </div>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:6px;">NIFTY DAY RANGE</div>
        <div style="display:flex;justify-content:space-between;font-size:0.60em;color:#333;margin-bottom:4px;">
            <span style="color:#ef4444;">L {nf_low:,.2f}</span>
            <span style="color:#22c55e;">H {nf_high:,.2f}</span>
        </div>
        <div class="bar-track" style="height:6px;">
            <div class="bar-fill" style="width:{nf_close_w}%;background:{nf_col};"></div>
        </div>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:6px;">INDIA VIX (VOLATILITY)</div>
        <div class="big-num" style="color:{vix_col};">{f'{vix:.2f}' if vix > 0 else '─'}</div>
        <div class="big-sub">{vix_sig}</div>
        <div class="ratio-track" style="margin-top:8px;">
            <div class="ratio-marker" style="left:{vix_pct:.0f}%;background:{vix_col};"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.58em;color:#1f1f1f;margin-top:4px;">
            <span>&lt;12 Low</span><span>12–18 Normal</span><span>18–25 Elevated</span><span>&gt;25 High</span>
        </div>
    </div>
</div>

<!-- M1 -->
<div class="card">
    <div class="card-label">M1 — SMART MONEY DIVERGENCE <span class="card-tag">FII CASH + F&amp;O</span></div>
    <div class="signal-chip" style="border-left-color:{m1c};">
        <span class="chip-sub">FII REAL INTENT</span>
        <span class="chip-verdict" style="color:{m1c};">{m1['verdict']}</span>
        <span class="chip-detail">{m1['verdict_detail']}</span>
    </div>
    <div>
        <div class="dt"><span class="dt-lbl">FII BUY</span><span class="dt-val" style="color:#22c55e;">₹{c['buy']:,.0f} Cr</span></div>
        <div class="dt"><span class="dt-lbl">FII SELL</span><span class="dt-val" style="color:#ef4444;">₹{c['sell']:,.0f} Cr</span></div>
        <div class="vs-bar"><div class="vs-g" style="width:{buy_w}%;"></div><div class="vs-r"></div></div>
        <div class="dt"><span class="dt-lbl" style="color:#888;font-weight:700;">FII NET</span><span class="dt-val" style="color:{fc(c['net'])};font-size:0.90em;">{cr(c['net'])}</span></div>
        {dii_row}
        <div class="dt"><span class="dt-lbl">DIRECTION</span><span class="dt-val" style="color:{fc(c['net'])};">{m1['cash_dir']}</span></div>
    </div>
    <div class="split">
        <div class="split-col">
            <span class="split-title">INDEX FUTURES</span>
            <div class="dt"><span class="dt-lbl">L</span><span class="dt-val" style="color:#22c55e;">₹{fi['long']:,.0f}</span></div>
            <div class="dt"><span class="dt-lbl">S</span><span class="dt-val" style="color:#ef4444;">₹{fi['short']:,.0f}</span></div>
            <div class="dt" style="border:none;"><span class="dt-lbl">NET</span><span class="dt-val" style="color:{fc(fi['net'])};">{cr(fi['net'])}</span></div>
        </div>
        <div class="split-col">
            <span class="split-title">STOCK FUTURES</span>
            <div class="dt"><span class="dt-lbl">L</span><span class="dt-val" style="color:#22c55e;">₹{fs['long']:,.0f}</span></div>
            <div class="dt"><span class="dt-lbl">S</span><span class="dt-val" style="color:#ef4444;">₹{fs['short']:,.0f}</span></div>
            <div class="dt" style="border:none;"><span class="dt-lbl">NET</span><span class="dt-val" style="color:{fc(fs['net'])};">{cr(fs['net'])}</span></div>
        </div>
    </div>
    {fut_warn}
</div>

<!-- M4 -->
<div class="card">
    <div class="card-label">M4 — SECTOR ROTATION MAP <span class="card-tag">BHAVCOPY</span></div>
    <div class="signal-chip" style="border-left-color:{m4c};">
        <span class="chip-sub">MARKET MODE</span>
        <span class="chip-verdict" style="color:{m4c};">{m4['risk_mode']}</span>
        <span class="chip-detail">{m4['signal']}</span>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:8px;">SECTOR PERFORMANCE</div>
        {sector_rows if sector_rows else '<p style="color:#1f1f1f;font-size:0.68em;">Add bhavcopy_csv.csv to market-data/daily/</p>'}
    </div>
    <div class="split">
        <div class="split-col">
            <span class="split-title">MARKET BREADTH</span>
            <div class="dt"><span class="dt-lbl">ADVANCES</span><span class="dt-val" style="color:#22c55e;">{adv:,}</span></div>
            <div class="dt"><span class="dt-lbl">DECLINES</span><span class="dt-val" style="color:#ef4444;">{dec:,}</span></div>
            <div class="dt" style="border:none;"><span class="dt-lbl">A/D RATIO</span><span class="dt-val" style="color:{adr_c};">{ad_r}</span></div>
            <div class="vs-bar"><div class="vs-g" style="width:{adv_w}%;"></div><div class="vs-r"></div></div>
        </div>
        <div class="split-col">
            <span class="split-title">DELIVERY &amp; LEADERS</span>
            <div class="dt" style="border:none;"><span class="dt-lbl">AVG DELIVERY</span><span class="dt-val" style="color:{del_c};">{del_}%</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:{del_}%;background:{del_c};"></div></div>
            <div style="font-size:0.61em;color:#2a2a2a;line-height:2.1;margin-top:4px;">
                <div>▲ {top3 if top3 else '─'}</div>
                <div>▼ {bot3 if bot3 else '─'}</div>
            </div>
        </div>
    </div>
</div>

<!-- M6 -->
<div class="card">
    <div class="card-label">M6 — INSTITUTIONAL CONVICTION <span class="card-tag">5-DAY FLOWS</span></div>
    <div class="signal-chip" style="border-left-color:{m6c};">
        <span class="chip-sub">CONVICTION TREND</span>
        <span class="chip-verdict" style="color:{m6c};">{m6['signal']}</span>
        <span class="chip-detail">DII vs FII 5-day net positioning</span>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:10px;">5-DAY NET FLOWS</div>
        <div style="margin-bottom:10px;">
            <div class="dt"><span class="dt-lbl">DII 5-DAY NET</span><span class="dt-val" style="color:{d5c};">{cr(d5)}</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:{d5w}%;background:{d5c};"></div></div>
        </div>
        <div>
            <div class="dt"><span class="dt-lbl">FII 5-DAY NET</span><span class="dt-val" style="color:{f5c};">{cr(f5)}</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:{f5w}%;background:{f5c};"></div></div>
        </div>
    </div>
    <div class="hint">
        DII buy + FII sell = DII absorbing exits<br>
        Both buying = strong rally support<br>
        DII accelerating = strong conviction
    </div>
</div>

<!-- M7 -->
<div class="card">
    <div class="card-label">M7 — LEVERAGE &amp; RISK METER <span class="card-tag">F&amp;O STRESS</span></div>
    <div class="signal-chip" style="border-left-color:{m7c};">
        <span class="chip-sub">MARKET RISK LEVEL</span>
        <span class="chip-verdict" style="color:{m7c};">{m7['risk_level']}</span>
        <span class="chip-detail">{m7['risk_detail']}</span>
    </div>
    <div class="split">
        <div class="split-col">
            <span class="split-title">F&amp;O BAN</span>
            <div class="big-num" style="color:{m7c};">{m7['ban_count']}</div>
            <div class="big-sub">STOCKS IN BAN</div>
            <div class="big-sub">{m7.get('ban_date','')}</div>
        </div>
        <div class="split-col">
            <span class="split-title">FII L/S RATIO</span>
            <div class="big-num" style="color:{lsc};">{ratio if ratio > 0 else '─'}</div>
            <div class="big-sub">{m7.get('fii_signal','NO DATA')}</div>
            <div class="ratio-track">
                <div class="ratio-marker" style="left:{ratio_pct:.0f}%;background:{lsc};"></div>
            </div>
        </div>
    </div>
    <div class="split">
        <div class="split-col">
            <span class="split-title">INDEX FUTURES</span>
            <div class="dt"><span class="dt-lbl">LONG</span><span class="dt-val" style="color:#22c55e;">{il:,.0f}</span></div>
            <div class="dt" style="border:none;"><span class="dt-lbl">SHORT</span><span class="dt-val" style="color:#ef4444;">{is_:,.0f}</span></div>
        </div>
        <div class="split-col">
            <span class="split-title">STOCK FUTURES</span>
            <div class="dt"><span class="dt-lbl">LONG</span><span class="dt-val" style="color:#22c55e;">{sl:,.0f}</span></div>
            <div class="dt" style="border:none;"><span class="dt-lbl">SHORT</span><span class="dt-val" style="color:#ef4444;">{ss:,.0f}</span></div>
        </div>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:6px;">STOCKS IN BAN</div>
        <div style="min-height:22px;line-height:2.4;">
            {ban_pills if ban_pills else '<span style="color:#1a1a1a;font-size:0.68em;">No stocks in ban today</span>'}
        </div>
    </div>
</div>

<!-- M8 -->
<div class="card">
    <div class="card-label">M8 — PROMOTER CONFIDENCE <span class="card-tag">INSIDER TRENDS</span></div>
    <div class="signal-chip" style="border-left-color:{m8c};">
        <span class="chip-sub">INSIDER SENTIMENT</span>
        <span class="chip-verdict" style="color:{m8c};">{m8['signal']}</span>
        <span class="chip-detail">Promoter bulk deal proxy</span>
    </div>
    <div class="split">
        <div class="split-col" style="text-align:center;padding:12px 8px;background:#030303;border:1px solid #111;">
            <div style="font-size:0.56em;color:#22c55e;letter-spacing:2px;margin-bottom:6px;">▲ BUYS</div>
            <div class="big-num" style="color:#22c55e;">{m8['buy_count']}</div>
            <div class="big-sub">transactions</div>
            <div style="font-size:0.72em;color:#155724;margin-top:6px;">{m8['companies']} cos.</div>
        </div>
        <div class="split-col" style="text-align:center;padding:12px 8px;background:#030303;border:1px solid #111;">
            <div style="font-size:0.56em;color:#ef4444;letter-spacing:2px;margin-bottom:6px;">▼ SELLS</div>
            <div class="big-num" style="color:#ef4444;">{m8['sell_count']}</div>
            <div class="big-sub">transactions</div>
            <div style="font-size:0.72em;color:#6e1f1f;margin-top:6px;">&nbsp;</div>
        </div>
    </div>
    <div>
        <div style="font-size:0.56em;color:#252525;letter-spacing:2px;margin-bottom:6px;">BUY / SELL SPLIT</div>
        <div class="vs-bar" style="height:7px;">
            <div class="vs-g" style="width:{m8buy_w}%;"></div>
            <div class="vs-r"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.58em;color:#252525;margin-top:4px;">
            <span>{m8buy_w}% buys</span><span>{m8sell_w}% sells</span>
        </div>
    </div>
    <div class="hint">
        3+ companies buying = bottom signal<br>
        Sells &gt; Buys = distribution phase<br>
        Buys &gt; Sells = insider accumulation
    </div>
</div>

</div><!-- /dash-grid -->

<div id="site-footer">
    <span>QUANTIS MARKET INTELLIGENCE · M1 · M4 · M6 · M7 · M8 · SOURCE: NSE INDIA</span>
    <span>For informational purposes only · Not investment advice</span>
</div>

<div id="bookmark-panel">
    <h3>SAVED REPORTS</h3>
    <ul id="bookmark-list"></ul>
</div>
<script>
    function togglePanel() {{
        const p = document.getElementById('bookmark-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    }}
    function showBookmarks() {{
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.getElementById('bookmark-list').innerHTML = bm.length === 0
            ? '<li style="color:#333;cursor:default;">No saved reports</li>'
            : bm.map((b,i) => `<li>${{b}}</li>`).join('');
    }}
    window.onload = function() {{ showBookmarks(); }};
    function toggleMenu() {{
        document.getElementById('nav-drawer').classList.toggle('open');
        document.getElementById('nav-overlay').classList.toggle('open');
    }}
</script>
</body>
</html>'''


    # M1 components
    c  = m1['cash']
    di = m1['dii_cash']
    fi = m1['index_fut']
    fs = m1['stock_fut']
    io = m1['index_opt']

    # M6 components
    m6c = m6['signal_col']
    m6_card = f"""
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
    </div>"""

    # M8 components
    m8c = m8['signal_col']
    m8_card = f"""
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
                <div class="data-row nb"><span class="lbl" style="font-weight:700;">COMPANIES</span><span style="color:#fff;font-weight:700;font-size:1.1em;">_</span></div>
            </div>
        </div>
    </div>"""

    dii_row = ''
    if di.get('net',0) != 0:
        dii_row = f'''
        <div class="data-row">
            <div>
                <div class="lbl">DII NET <span class="sub">Buy ₹{di['buy']:,.0f} · Sell ₹{di['sell']:,.0f}</span></div>
            </div>
            <div style="color:{fc(di['net'])};font-weight:700;">{cr(di['net'])}</div>
        </div>'''

    fut_warn = ''
    if m1['fut_dir'] == 'NO DATA':
        fut_warn = '<div style="color:#ff9944;font-size:0.65em;padding:4px 0 2px 0;">⚠ Add fii_stats.xls for complete derivatives picture</div>'

    m1_card = f'''
    <div class="card">
        <div class="card-head">M1 — SMART MONEY DIVERGENCE <span class="badge">FII CASH + F&O</span></div>
        <div class="verdict-box" style="border-color:{m1['verdict_col']};">
            <div class="verdict-lbl">FII REAL INTENT</div>
            <div class="verdict-val" style="color:{m1['verdict_col']};">{m1['verdict']}</div>
            <div class="verdict-detail">{m1['verdict_detail']}</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">FII CASH EQUITY</div>
                <div class="data-row"><span class="lbl">BUY</span><span style="color:#00cc44;font-weight:700;">₹{c['buy']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SELL</span><span style="color:#ff3333;font-weight:700;">₹{c['sell']:,.0f} Cr</span></div>
                <div class="data-row nb"><span class="lbl" style="color:#aaa;font-weight:700;">NET</span><span style="color:{fc(c['net'])};font-weight:700;font-size:1.1em;">{cr(c['net'])}</span></div>
                <div class="pill" style="color:{fc(c['net'])};border-color:{fc(c['net'])};">{m1['cash_dir']}</div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">INDEX FUTURES</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">₹{fi['long']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">₹{fi['short']:,.0f} Cr</span></div>
                <div class="data-row nb"><span class="lbl" style="color:#aaa;font-weight:700;">NET</span><span style="color:{fc(fi['net'])};font-weight:700;font-size:1.1em;">{cr(fi['net'])}</span></div>
                <div class="pill" style="color:{fc(fi['net'])};border-color:{fc(fi['net'])};">{m1['fut_dir']}</div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">STOCK FUTURES</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">₹{fs['long']:,.0f} Cr</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">₹{fs['short']:,.0f} Cr</span></div>
                <div class="data-row nb"><span class="lbl" style="color:#aaa;font-weight:700;">NET</span><span style="color:{fc(fs['net'])};font-weight:700;font-size:1.1em;">{cr(fs['net'])}</span></div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">SUMMARY</div>
                <div class="data-row"><span class="lbl">INDEX OPT NET</span><span style="color:{fc(io['net'])};font-weight:700;">{cr(io['net'])}</span></div>
                <div class="data-row"><span class="lbl">TOTAL NET</span><span style="color:{fc(m1['total_net'])};font-weight:700;">{cr(m1['total_net'])}</span></div>
                <div class="data-row nb"><span class="lbl">RISK</span><span style="color:#888;font-weight:700;">{m1['risk']}</span></div>
            </div>
        </div>
        {dii_row}
        {fut_warn}
        <div class="hint-box">
            Cash SELL + Fut LONG &nbsp;= HEDGE — FII nahi nikal raha (Oct 2021 pattern)<br>
            Cash SELL + Fut SHORT = REAL EXIT — Genuine exit, avoid fresh longs<br>
            Cash BUY &nbsp;+ Fut LONG &nbsp;= ACCUMULATE — Strong bullish conviction<br>
            Cash BUY &nbsp;+ Fut SHORT = PROFIT BOOKING — Cautious on upside<br>
            <span style="color:#111;">Data: {m1['date']}</span>
        </div>
    </div>'''

    # M4 components
    sectors = m4.get('sectors', {})
    ranked  = sorted(sectors.items(), key=lambda x:x[1], reverse=True)

    sector_rows = ''
    for s, v in ranked:
        c_   = '#00cc44' if v > 0 else '#ff3333'
        bw   = min(130, abs(v) * 28)
        arr  = '▲' if v > 0 else '▼'
        sign = '+' if v > 0 else ''
        sector_rows += f'''
        <div class="sector-row">
            <span class="s-name">{s}</span>
            <div class="s-bar-bg"><div style="background:{c_};height:5px;width:{bw}px;border-radius:2px;"></div></div>
            <span style="color:{c_};font-size:0.74em;font-weight:700;width:68px;text-align:right;flex-shrink:0;">{arr} {sign}{v:.2f}%</span>
        </div>'''

    adv   = m4.get('advances', 0)
    dec   = m4.get('declines', 0)
    unch  = m4.get('unchanged', 0)
    del_  = m4.get('avg_delivery', 0)
    del_c = '#00cc44' if del_ >= 50 else ('#ff9944' if del_ >= 35 else '#ff3333')
    ad_r  = round(adv/dec, 2) if dec > 0 else adv
    adr_c = '#00cc44' if ad_r >= 1.5 else ('#ff9944' if ad_r >= 0.8 else '#ff3333')

    top3  = ' · '.join(f'<span style="color:#00cc44">{s}</span>({v:+.2f}%)' for s,v in m4.get('top_3',[]))
    bot3  = ' · '.join(f'<span style="color:#ff3333">{s}</span>({v:+.2f}%)' for s,v in m4.get('bottom_3',[]))

    m4_card = f'''
    <div class="card">
        <div class="card-head">M4 — SECTOR ROTATION MAP <span class="badge">BHAVCOPY</span></div>
        <div class="verdict-box" style="border-color:{m4['signal_col']};">
            <div class="verdict-lbl">MARKET MODE</div>
            <div class="verdict-val" style="color:{m4['signal_col']};">{m4['risk_mode']}</div>
            <div class="verdict-detail">{m4['signal']}</div>
        </div>
        <div style="margin-bottom:10px;">
            <div class="inner-head" style="margin-bottom:8px;">SECTOR PERFORMANCE TODAY</div>
            {sector_rows if sector_rows else '<div style="color:#222;font-size:0.75em;padding:6px 0;">Add bhavcopy_csv.csv to market-data/daily/</div>'}
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">MARKET BREADTH</div>
                <div class="data-row"><span class="lbl">ADVANCES</span><span style="color:#00cc44;font-weight:700;font-size:1.1em;">{adv:,}</span></div>
                <div class="data-row"><span class="lbl">DECLINES</span><span style="color:#ff3333;font-weight:700;font-size:1.1em;">{dec:,}</span></div>
                <div class="data-row"><span class="lbl">UNCHANGED</span><span style="color:#555;font-weight:700;">{unch:,}</span></div>
                <div class="data-row nb"><span class="lbl">A/D RATIO</span><span style="color:{adr_c};font-weight:700;">{ad_r}</span></div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">DELIVERY &amp; LEADERS</div>
                <div class="data-row"><span class="lbl">AVG DELIVERY</span><span style="color:{del_c};font-weight:700;font-size:1.1em;">{del_}%</span></div>
                <div style="font-size:0.72em;margin-top:8px;line-height:2.1;">
                    <div>▲ {top3 if top3 else '─'}</div>
                    <div>▼ {bot3 if bot3 else '─'}</div>
                </div>
            </div>
        </div>
        <div class="hint-box">
            IT + Pharma lead = RISK-OFF — Defensive rotation<br>
            Auto + Metal + Energy lead = RISK-ON — Cyclicals<br>
            Banking lead = liquidity positive, rate cut expected<br>
            A/D &gt; 2 = broad rally · A/D &lt; 0.7 = broad selloff
        </div>
    </div>'''

    # M7 components
    ban_pills = ''.join(f'<span class="ban-pill">{s}</span>' for s in m7.get('ban_stocks',[]))
    ratio     = m7['fii_ls_ratio']
    lsc       = '#00cc44' if ratio > 1.2 else ('#ff3333' if 0 < ratio < 0.85 else '#888888')
    il        = m7['fii_idx_long']
    is_       = m7['fii_idx_short']
    sl        = m7['fii_stk_long']
    ss        = m7['fii_stk_short']

    m7_card = f'''
    <div class="card">
        <div class="card-head">M7 — LEVERAGE &amp; RISK METER <span class="badge">F&O STRESS</span></div>
        <div class="verdict-box" style="border-color:{m7['risk_col']};">
            <div class="verdict-lbl">MARKET RISK LEVEL</div>
            <div class="verdict-val" style="color:{m7['risk_col']};">{m7['risk_level']}</div>
            <div class="verdict-detail">{m7['risk_detail']}</div>
        </div>
        <div class="inner-grid">
            <div class="inner-cell">
                <div class="inner-head">F&amp;O BAN LIST</div>
                <div style="font-size:2.8em;font-weight:700;color:{m7['risk_col']};line-height:1;margin:6px 0 3px 0;">{m7['ban_count']}</div>
                <div style="font-size:0.62em;color:#444;letter-spacing:1px;margin-bottom:8px;">STOCKS IN BAN · {m7.get('ban_date','')}</div>
                <div style="font-size:0.67em;color:#222;line-height:1.9;">
                    0-3 = normal · 3-8 = watch<br>8+ = elevated risk
                </div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">FII L/S RATIO</div>
                <div style="font-size:2.4em;font-weight:700;color:{lsc};line-height:1;margin:6px 0 6px 0;">{ratio if ratio > 0 else '─'}</div>
                <div class="pill" style="color:{lsc};border-color:{lsc};margin-bottom:8px;">{m7.get('fii_signal','NO DATA')}</div>
                <div style="font-size:0.67em;color:#222;line-height:1.9;">
                    &gt;1.3 = bullish · &lt;0.8 = bearish
                </div>
            </div>
        </div>
        <div class="inner-grid" style="margin-top:1px;">
            <div class="inner-cell">
                <div class="inner-head">FII INDEX FUTURES (contracts)</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">{il:,.0f}</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">{is_:,.0f}</span></div>
                <div class="data-row nb"><span class="lbl" style="color:#aaa;font-weight:700;">NET</span><span style="color:{fc(il-is_)};font-weight:700;">{il-is_:+,.0f}</span></div>
            </div>
            <div class="inner-cell">
                <div class="inner-head">FII STOCK FUTURES (contracts)</div>
                <div class="data-row"><span class="lbl">LONG</span><span style="color:#00cc44;font-weight:700;">{sl:,.0f}</span></div>
                <div class="data-row"><span class="lbl">SHORT</span><span style="color:#ff3333;font-weight:700;">{ss:,.0f}</span></div>
                <div class="data-row nb"><span class="lbl" style="color:#aaa;font-weight:700;">NET</span><span style="color:{fc(sl-ss)};font-weight:700;">{sl-ss:+,.0f}</span></div>
            </div>
        </div>
        <div style="margin-top:10px;">
            <div class="inner-head" style="margin-bottom:6px;">STOCKS IN F&amp;O BAN</div>
            <div style="min-height:22px;line-height:2.2;">
                {ban_pills if ban_pills else '<span style="color:#1a1a1a;font-size:0.72em;">No stocks in ban today</span>'}
            </div>
        </div>
        <div class="hint-box">
            FII L/S &lt; 0.7 = heavy short = crash risk elevated<br>
            FII L/S &gt; 1.5 = heavily long = strong market support<br>
            Ban 8+ stocks = high leverage / concentration risk<br>
            <span style="color:#111;">Data: {m7.get('date', TODAY_STR)}</span>
        </div>
    </div>'''

    m1c = m1['verdict_col']
    m4c = m4['signal_col']
    m7c = m7['risk_col']

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QUANTIS — Market Intelligence</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{
            font-family: 'IBM Plex Mono', monospace;
            background: #000;
            color: #fff;
            padding-bottom: 60px;
        }}
        #site-header {{
            background: #000;
            border-bottom: 2px solid #ff6600;
            padding: 14px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        #site-logo {{
            font-size: 1.6em;
            font-weight: 700;
            color: #fff;
            letter-spacing: 3px;
        }}
        #nav-drawer {{
            position: fixed;
            top: 0; right: -260px;
            width: 240px;
            height: 100vh;
            background: #050505;
            border-left: 1px solid #1a1a1a;
            z-index: 999;
            padding: 20px 0;
            transition: right 0.25s ease;
        }}
        #nav-drawer.open {{ right: 0; }}
        #nav-drawer-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 20px 16px;
            border-bottom: 1px solid #1a1a1a;
            margin-bottom: 10px;
        }}
        .drawer-link {{
            display: block;
            padding: 14px 20px;
            color: #555;
            text-decoration: none;
            font-size: 0.80em;
            font-weight: 700;
            letter-spacing: 3px;
            border-bottom: 1px solid #0f0f0f;
        }}
        .drawer-link:hover {{ color: #fff; background: #0a0a0a; }}
        .drawer-link.active {{ color: #ff6600; }}
        #nav-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.6);
            z-index: 998;
        }}
        #nav-overlay.open {{ display: block; }}
        #bookmark-panel {{
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
        }}
        #bookmark-panel h3 {{
            color: #ff6600;
            letter-spacing: 3px;
            font-size: 0.70em;
            border-bottom: 1px solid #1a1a1a;
            padding-bottom: 8px;
            margin-bottom: 10px;
        }}
        #bookmark-list li {{
            font-size: 0.74em;
            color: #888;
            padding: 7px 0;
            cursor: pointer;
            border-bottom: 1px solid #0f0f0f;
        }}
        #bookmark-list li:hover {{ color: #fff; }}
        #ticker-bar {{
            background: #fff;
            color: #000;
            font-size: 0.75em;
            font-weight: 700;
            padding: 5px 0;
            overflow: hidden;
            white-space: nowrap;
            border-bottom: 1px solid #ddd;
        }}
        #ticker-content {{
            display: inline-block;
            animation: scroll-ticker 90s linear infinite;
            padding-left: 100%;
        }}
        #ticker-content span {{ margin-right: 60px; color: #000; }}
        @keyframes scroll-ticker {{
            0%   {{ transform: translateX(0); }}
            100% {{ transform: translateX(-100%); }}
        }}
        /* ---- market page section header ---- */
        .page-header {{
            padding: 20px 24px 10px;
            border-bottom: 1px solid #111;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .section-title {{
            font-size: 0.70em;
            font-weight: 700;
            color: #ff6600;
            letter-spacing: 3px;
        }}
        .page-date {{
            font-size: 0.65em;
            color: #333;
            letter-spacing: 1px;
        }}
        #main-content {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 24px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 1px;
            background: #111111;
        }}
        .card {{ background:#000000; padding:16px 18px; }}
        .card-head {{
            font-size: 0.63em;
            letter-spacing: 2px;
            color: #444444;
            border-bottom: 1px solid #1a1a1a;
            padding-bottom: 6px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .badge {{ font-size:0.9em; padding:1px 6px; border:1px solid #1a1a1a; color:#333333; letter-spacing:1px; }}
        .verdict-box {{
            border: 1px solid #222222;
            background: #060606;
            padding: 12px 14px;
            margin-bottom: 12px;
            text-align: center;
        }}
        .verdict-lbl  {{ font-size:0.6em; color:#333; letter-spacing:3px; margin-bottom:4px; }}
        .verdict-val  {{ font-size:1.3em; font-weight:700; letter-spacing:2px; margin-bottom:6px; }}
        .verdict-detail {{ font-size:0.65em; color:#444; line-height:1.6; }}
        .inner-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1px;
            background: #111111;
            margin-bottom: 1px;
        }}
        .inner-cell {{ background:#000000; padding:10px 12px; }}
        .inner-head  {{ font-size:0.62em; color:#444444; letter-spacing:2px; margin-bottom:6px; }}
        .data-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
            border-bottom: 1px solid #0d0d0d;
        }}
        .data-row.nb {{ border:none; }}
        .lbl {{ color:#555555; font-size:0.82em; letter-spacing:0.5px; }}
        .sub {{ color:#333333; font-size:0.8em; margin-left:6px; }}
        .pill {{
            margin-top: 6px;
            padding: 3px 8px;
            background: #080808;
            border: 1px solid #1a1a1a;
            text-align: center;
            font-size: 0.63em;
            font-weight: 700;
            letter-spacing: 2px;
        }}
        .sector-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
            border-bottom: 1px solid #080808;
        }}
        .s-name {{ color:#666666; font-size:0.72em; width:76px; flex-shrink:0; }}
        .s-bar-bg {{ flex:1; background:#0a0a0a; height:5px; border-radius:2px; overflow:hidden; }}
        .ban-pill {{
            display: inline-block;
            padding: 2px 8px;
            margin: 2px;
            background: #0a0a0a;
            border: 1px solid #1a1a1a;
            color: #ff9944;
            font-size: 0.7em;
            letter-spacing: 1px;
        }}
        .hint-box {{
            margin-top: 10px;
            padding: 7px 10px;
            background: #050505;
            font-size: 0.62em;
            color: #222222;
            line-height: 2;
            border-left: 2px solid #0d0d0d;
        }}
        #footer {{
            background: #000000;
            border-top: 1px solid #111111;
            padding: 8px 24px;
            display: flex;
            justify-content: space-between;
            font-size: 0.62em;
            color: #1a1a1a;
            letter-spacing: 1px;
            margin-top: 2px;
        }}
        @media (max-width:900px) {{ #main-content {{ grid-template-columns:1fr; }} }}
    </style>
</head>
<body>

    <div id="site-header">
        <div id="site-logo">Quantis</div>
        <button id="hamburger" onclick="toggleMenu()" style="background:none;border:none;cursor:pointer;color:#888;font-size:1.4em;padding:0;line-height:1;">&#9776;</button>
    </div>
    <div id="nav-drawer">
        <div id="nav-drawer-header">
            <span style="color:#ff6600;font-size:0.75em;letter-spacing:3px;font-weight:700;">MENU</span>
            <button onclick="toggleMenu()" style="background:none;border:none;color:#444;cursor:pointer;font-size:1.2em;">&#10005;</button>
        </div>
        <nav id="drawer-nav">
            <a href="index.html" class="drawer-link">HOME</a>
            <a href="research.html" class="drawer-link">RESEARCH</a>
            <a href="market.html" class="drawer-link active">MARKET</a>
            <a href="economy.html" class="drawer-link">ECONOMY</a>
            <a href="#" class="drawer-link" onclick="togglePanel();toggleMenu();">SAVED</a>
        </nav>
    </div>
    <div id="nav-overlay" onclick="toggleMenu()"></div>

<div id="ticker-bar">
    <div id="ticker-content">
        <span>NIFTY 50 &nbsp; 23,114.50 &nbsp; ▲ +0.00%</span><span>SENSEX &nbsp; 74,532.96 &nbsp; ▲ +0.00%</span><span>BANK NIFTY &nbsp; 53,427.05 &nbsp; ▲ +0.00%</span><span>S&amp;P 500 &nbsp; 6,606.49 &nbsp; ▼ -0.27%</span><span>NASDAQ &nbsp; 22,090.69 &nbsp; ▼ -0.28%</span><span>DOW JONES &nbsp; 46,021.43 &nbsp; ▼ -0.44%</span><span>GOLD &nbsp; $4,657.30 &nbsp; ▲ +1.23%</span><span>CRUDE OIL &nbsp; $95.75 &nbsp; ▼ -0.41%</span><span>USD/INR &nbsp; ₹93.58 &nbsp; ▲ +0.36%</span><span>NIFTY 50 &nbsp; 23,114.50 &nbsp; ▲ +0.00%</span><span>SENSEX &nbsp; 74,532.96 &nbsp; ▲ +0.00%</span><span>BANK NIFTY &nbsp; 53,427.05 &nbsp; ▲ +0.00%</span><span>S&amp;P 500 &nbsp; 6,606.49 &nbsp; ▼ -0.27%</span><span>NASDAQ &nbsp; 22,090.69 &nbsp; ▼ -0.28%</span><span>DOW JONES &nbsp; 46,021.43 &nbsp; ▼ -0.44%</span><span>GOLD &nbsp; $4,657.30 &nbsp; ▲ +1.23%</span><span>CRUDE OIL &nbsp; $95.75 &nbsp; ▼ -0.41%</span><span>USD/INR &nbsp; ₹93.58 &nbsp; ▲ +0.36%</span>
    </div>
</div>

<div class="page-header">
    <span class="section-title">MARKET INTELLIGENCE</span>
    <span class="page-date">{TODAY_STR} &nbsp;·&nbsp; <span style="color:{m7c};font-weight:700;">{m7['risk_level']} RISK</span> &nbsp;·&nbsp; <span style="color:{m4c};">{m4['risk_mode']}</span></span>
</div>

<div id="main-content">
    {m6_card}
    {m1_card}
    {m8_card}
    {m4_card}
    {m7_card}
</div>

<div id="footer">
    <span>QUANTIS MARKET INTELLIGENCE · M1 + M4 + M7 · SOURCE: NSE INDIA</span>
    <span>For informational purposes only · Not investment advice</span>
</div>

<div id="bookmark-panel">
    <h3>SAVED REPORTS</h3>
    <ul id="bookmark-list"></ul>
</div>
<script>
    function togglePanel() {{
        const p = document.getElementById('bookmark-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    }}
    function showBookmarks() {{
        let bm = JSON.parse(localStorage.getItem('bookmarks') || '[]');
        document.getElementById('bookmark-list').innerHTML = bm.length === 0
            ? '<li style="color:#333;cursor:default;">No saved reports</li>'
            : bm.map((b,i) => `<li>${{b}}</li>`).join('');
    }}
    window.onload = function() {{ showBookmarks(); }};
    function toggleMenu() {{
        document.getElementById('nav-drawer').classList.toggle('open');
        document.getElementById('nav-overlay').classList.toggle('open');
    }}
</script>
</body>
</html>'''

# ================================================================
#  MAIN
# ================================================================

if __name__ == '__main__':
    print("\n" + "="*55)
    print(f"  QUANTIS — MARKET INTELLIGENCE  |  {TODAY_STR}")
    print("="*55)

    m1 = process_m1()
    m2 = process_m2()
    m3 = process_m3()
    m4 = process_m4()
    m6 = process_m6()
    m7 = process_m7()
    m8 = process_m8()

    print("\n" + "─"*50)
    print("  Building market.html...")

    html = build_html(m1, m2, m3, m4, m6, m7, m8)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    with open('market_data.json', 'w') as f:
        json.dump({'m1':m1,'m2':m2,'m3':m3,'m4':m4,'m6':m6,'m7':m7,'m8':m8,'date':TODAY_STR}, f, indent=2, default=str)

    print(f"\n{'='*55}")
    print(f"  market.html ready — open in browser")
    print(f"  market_data.json saved")
    print(f"{'='*55}")
    print(f"""
  DAILY FILES — roz NSE se download karo:
  ─────────────────────────────────────────
  market-data/daily/fii-dii-combined-latest.csv
    nseindia.com/market-data/fii-dii-activity → Download (.csv)

  market-data/daily/fii_stats_[date].xls
    nseindia.com/all-reports → Derivatives tab
    → FII Derivatives Statistics → Download

  market-data/daily/bhavcopy_csv.csv
    nseindia.com/all-reports → Equity tab → Bhavcopy → CSV

  WEEKLY FILES — har hafte:
  ─────────────────────────────────────────
  market-data/weekly/fao_participant_oi_[date].csv
    nseindia.com/all-reports → Derivatives tab
    → Participant wise Open Interest → Download

  market-data/weekly/fo_ban_csv.csv
    nseindia.com/all-reports → Derivatives tab
    → Securities in F&O Ban → Download
  ─────────────────────────────────────────
""")