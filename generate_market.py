# ================================================================
#  QUANTIS — MARKET DASHBOARD GENERATOR  (v2 — scroll + sort + NSE500)
#
#  market-data/ folder mein yeh files daalo:
#  - PR{date}.zip              -> Bhavcopy (required)
#  - MA{date}.csv              -> Market Activity (required)
#  - MTO_{date}.DAT            -> Delivery data (required)
#  - bulk.csv                  -> Bulk deals (required)
#  - shortselling_{date}.csv   -> Short selling (optional)
#  - fii_dii.csv               -> FII/DII (optional, manual)
# ================================================================

import os, csv, zipfile, glob
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf

load_dotenv()
WEBSITE_TITLE = "Quantis"
MARKET_FOLDER = "market-data"

def find_pr_zip():
    z = glob.glob(os.path.join(MARKET_FOLDER,"PR*.zip")); return sorted(z)[-1] if z else None
def find_ma():
    f = glob.glob(os.path.join(MARKET_FOLDER,"MA*.csv")); return sorted(f)[-1] if f else None
def find_mto():
    f = glob.glob(os.path.join(MARKET_FOLDER,"MTO_*.DAT")); return sorted(f)[-1] if f else None
def find_short():
    f = glob.glob(os.path.join(MARKET_FOLDER,"shortselling*.csv")); return sorted(f)[-1] if f else None

def fetch_ticker():
    symbols={"NIFTY 50":"^NSEI","SENSEX":"^BSESN","BANK NIFTY":"^NSEBANK",
             "S&P 500":"^GSPC","NASDAQ":"^IXIC","DOW JONES":"^DJI","GOLD":"GC=F","CRUDE OIL":"CL=F","USD/INR":"INR=X"}
    items=[]
    for name,sym in symbols.items():
        try:
            hist=yf.Ticker(sym).history(period="2d")
            if hist.empty: raise ValueError()
            cur=hist['Close'].iloc[-1]; prev=hist['Close'].iloc[-2] if len(hist)>=2 else cur
            chg=((cur-prev)/prev)*100; ar="▲" if chg>=0 else "▼"; sg="+" if chg>=0 else ""
            if name in ["GOLD","CRUDE OIL"]: val=f"${cur:,.2f}"
            elif name=="USD/INR": val=f"₹{cur:.2f}"
            else: val=f"{cur:,.2f}"
            items.append(f"{name} &nbsp; {val} &nbsp; {ar} {sg}{chg:.2f}%")
        except: items.append(f"{name} &nbsp; -- &nbsp; N/A")
    return items

def get_nifty500_names(pr_zip):
    """Get top 500 stocks by market cap — security names (uppercase)"""
    sym_mcap=[]
    mcap_f=glob.glob(os.path.join(MARKET_FOLDER,"mcap*.csv"))
    if not mcap_f and pr_zip:
        try:
            with zipfile.ZipFile(pr_zip) as z:
                mc=[f for f in z.namelist() if f.lower().startswith('mcap')]
                if mc:
                    with z.open(mc[0]) as f:
                        for row in csv.DictReader(line.decode('utf-8') for line in f):
                            sym=row.get('Symbol','').strip(); series=row.get('Series','').strip()
                            sec=row.get('Security Name','').strip()
                            mcap_raw=list(row.values())[-1].strip().replace(',','')
                            if series=='EQ' and sym:
                                try: sym_mcap.append((sec.strip().upper(),float(mcap_raw)))
                                except: pass
        except: pass
    else:
        f=sorted(mcap_f)[-1] if mcap_f else None
        if f:
            with open(f) as file:
                for row in csv.DictReader(file):
                    sec=row.get('Security Name','').strip(); series=row.get('Series','').strip()
                    mcap_raw=list(row.values())[-1].strip().replace(',','')
                    if series=='EQ' and sec:
                        try: sym_mcap.append((sec.upper(),float(mcap_raw)))
                        except: pass
    sym_mcap.sort(key=lambda x:x[1],reverse=True)
    return {name for name,_ in sym_mcap[:500]}

def parse_ma(ma_file):
    result={'traded_val':0,'traded_qty':0,'trades':0,'mktcap':0,'indices':{},'sectors':{}}
    if not ma_file or not os.path.exists(ma_file): return result
    sector_map={'Nifty IT':'IT','Nifty Pharma':'PHARMA','Nifty Bank':'BANKING','Nifty PSU Bank':'PSU BANK',
                'Nifty Auto':'AUTO','Nifty Metal':'METALS','Nifty FMCG':'FMCG','Nifty Energy':'ENERGY',
                'Nifty Realty':'REALTY','Nifty Infra':'INFRA','Nifty Media':'MEDIA','Nifty Fin Service':'FIN SERV'}
    try:
        with open(ma_file,encoding='utf-8',errors='ignore') as f: lines=f.readlines()
        for line in lines:
            p=[x.strip() for x in line.split(',')]
            if 'Traded Value' in line:
                try: result['traded_val']=float(p[-1].replace(',',''))
                except: pass
            if 'Traded Quantity' in line:
                try: result['traded_qty']=float(p[-1].replace(',',''))
                except: pass
            if 'Number of Trades' in line:
                try: result['trades']=int(p[-1].replace(',','').split('.')[0])
                except: pass
            if 'Market Capitalisation' in line:
                try: result['mktcap']=float(p[-1].replace(',',''))
                except: pass
            if len(p)>=8:
                name=p[1].strip()
                try:
                    prev=float(p[2].replace(',','').strip()); close=float(p[6].replace(',','').strip())
                    gain=float(p[7].replace(',','').strip()); chg=(gain/prev)*100 if prev else 0
                    result['indices'][name]={'close':close,'chg':chg,'gain':gain,'prev':prev,
                        'open':float(p[3].replace(',','').strip()),'high':float(p[4].replace(',','').strip()),
                        'low':float(p[5].replace(',','').strip())}
                    if name in sector_map: result['sectors'][sector_map[name]]=chg
                except: pass
    except Exception as e: print(f"  [MA] {e}")
    return result

def parse_pr(pr_zip, nifty500_names):
    key_indices={}; gainers=[]; losers=[]; highs=[]; lows=[]; top_value=[]
    KEY_NAMES=['Nifty 50','Nifty Bank','Nifty IT','Nifty Pharma','Nifty Auto',
               'Nifty Metal','Nifty FMCG','Nifty Realty','Nifty Energy',
               'NIFTY MIDCAP 100','NIFTY SMLCAP 100','Nifty Next 50','Nifty 500']
    if not pr_zip: return key_indices,gainers,losers,highs,lows,top_value
    try:
        with zipfile.ZipFile(pr_zip) as z:
            names=z.namelist()
            pr_f=[f for f in names if f.lower().startswith('pr') and f.endswith('.csv')]
            if pr_f:
                with z.open(pr_f[0]) as f:
                    for row in csv.DictReader(line.decode('utf-8') for line in f):
                        name=row.get('SECURITY','').strip()
                        if name in KEY_NAMES:
                            try:
                                prev=float(row['PREV_CL_PR'].replace(',','').strip())
                                close=float(row['CLOSE_PRICE'].replace(',','').strip())
                                high=float(row['HIGH_PRICE'].replace(',','').strip())
                                low=float(row['LOW_PRICE'].replace(',','').strip())
                                hi52=row.get('HI_52_WK','').replace(',','').strip()
                                lo52=row.get('LO_52_WK','').replace(',','').strip()
                                chg=((close-prev)/prev)*100 if prev else 0
                                key_indices[name]={'prev':prev,'close':close,'high':high,'low':low,'chg':chg,'hi52':hi52,'lo52':lo52}
                            except: pass
            gl_f=[f for f in names if f.lower().startswith('gl') and f.endswith('.csv')]
            if gl_f:
                with z.open(gl_f[0]) as f:
                    for row in csv.DictReader(line.decode('utf-8') for line in f):
                        gl=row.get('GAIN_LOSS','').strip(); name=row.get('SECURITY','').strip()
                        pct=row.get('PERCENT_CG','').strip(); price=row.get('CLOSE_PRIC','').strip()
                        if not name or not gl: continue
                        in500 = (not nifty500_names) or (name.upper() in nifty500_names)
                        try:
                            pf=float(pct); prf=float(price)
                            if gl=='G' and in500: gainers.append({'name':name,'pct':pf,'price':prf})
                            elif gl=='L' and in500: losers.append({'name':name,'pct':pf,'price':prf})
                        except: pass
                gainers.sort(key=lambda x:x['pct'],reverse=True)
                losers.sort(key=lambda x:x['pct'])
            bh_f=[f for f in names if f.lower().startswith('bh') and f.endswith('.csv')]
            if bh_f:
                with z.open(bh_f[0]) as f:
                    for row in csv.DictReader(line.decode('utf-8') for line in f):
                        sym=row.get('SYMBOL','').strip(); hl=row.get('HIGH/LOW','').strip()
                        sec=row.get('SECURITY','').strip()
                        if row.get('SERIES','').strip()=='EQ':
                            label=f"{sym} — {sec}" if sec else sym
                            if hl=='H': highs.append({'sym':sym,'name':sec,'label':label})
                            elif hl=='L': lows.append({'sym':sym,'name':sec,'label':label})
            tt_f=[f for f in names if f.lower().startswith('tt') and f.endswith('.csv')]
            if tt_f:
                with z.open(tt_f[0]) as f:
                    for row in csv.DictReader(line.decode('utf-8') for line in f):
                        name=row.get('SECURITY','').strip(); val=row.get('NET_TRDVAL','').replace(',','').strip()
                        prev=row.get('PREV_CL_PR','').replace(',','').strip(); close=row.get('CLOSE_PRIC','').replace(',','').strip()
                        if not name or not val: continue
                        try:
                            vc=float(val)/1e7; pf=float(prev); cf=float(close)
                            chg=((cf-pf)/pf)*100 if pf else 0
                            top_value.append({'name':name,'val_cr':vc,'chg':chg,'close':cf})
                        except: pass
    except Exception as e: print(f"  [PR] {e}")
    return key_indices, gainers, losers, highs, lows, top_value[:15]

def parse_mto(mto_file):
    stocks=[]; total_d=0; cnt=0; advances=0; declines=0; unchanged=0
    if mto_file and os.path.exists(mto_file):
        try:
            with open(mto_file) as f:
                for line in f:
                    p=[x.strip() for x in line.split(',')]
                    if len(p)>=7 and p[0]=='20' and p[3]=='EQ':
                        try:
                            pct=float(p[6]); total_d+=pct; cnt+=1
                            stocks.append({'name':p[2],'pct':pct})
                        except: pass
            stocks.sort(key=lambda x:x['pct'],reverse=True)
        except Exception as e: print(f"  [MTO] {e}")
    pr_zip=find_pr_zip()
    if pr_zip:
        try:
            with zipfile.ZipFile(pr_zip) as z:
                gl_f=[f for f in z.namelist() if f.lower().startswith('gl') and f.endswith('.csv')]
                if gl_f:
                    with z.open(gl_f[0]) as f:
                        for row in csv.DictReader(line.decode('utf-8') for line in f):
                            gl=row.get('GAIN_LOSS','').strip()
                            if gl=='G': advances+=1
                            elif gl=='L': declines+=1
                            elif row.get('SECURITY','').strip(): unchanged+=1
        except: pass
    avg_d=total_d/cnt if cnt else 0
    return stocks, avg_d, advances, declines, unchanged

def parse_bulk():
    deals=[]
    f=glob.glob(os.path.join(MARKET_FOLDER,"bulk*.csv"))
    if not f: return deals
    try:
        with open(f[0],encoding='utf-8') as file:
            for row in csv.DictReader(file):
                sym=row.get('Symbol','').strip(); client=row.get('Client Name','').strip()
                bs=row.get('Buy/Sell','').strip(); price=row.get('Trade Price / Wght. Avg. Price','').strip()
                qty=row.get('Quantity Traded','').strip()
                if sym and client: deals.append({'sym':sym,'client':client,'bs':bs,'price':price,'qty':qty})
    except Exception as e: print(f"  [Bulk] {e}")
    return deals

def parse_short(short_file):
    stocks=[]
    if not short_file or not os.path.exists(short_file): return stocks
    try:
        with open(short_file,encoding='utf-8') as f:
            rows=list(csv.DictReader(f))
        rows.sort(key=lambda x:int(x.get('Quantity','0').replace(',','')),reverse=True)
        for r in rows: stocks.append({'sym':r.get('Symbol Name','').strip(),'name':r.get('Security Name','').strip(),'qty':r.get('Quantity','').strip()})
    except Exception as e: print(f"  [Short] {e}")
    return stocks

def parse_fii():
    f=os.path.join(MARKET_FOLDER,"fii_dii.csv")
    if not os.path.exists(f): return None
    try:
        with open(f) as file:
            rows=list(csv.DictReader(file))
            if rows:
                r=rows[-1]
                return {'fii_buy':r.get('FII Buy','?'),'fii_sell':r.get('FII Sell','?'),
                        'fii_net':r.get('FII Net','?'),'dii_buy':r.get('DII Buy','?'),
                        'dii_sell':r.get('DII Sell','?'),'dii_net':r.get('DII Net','?')}
    except: pass
    return None

def cc(v): return '#00cc44' if v>0 else ('#ff3333' if v<0 else '#888')
def arr(v): return '▲' if v>=0 else '▼'
def sg(v): return '+' if v>=0 else ''
def fcr(v): return f"₹{v/100:.1f}K Cr" if v>=1000 else f"₹{v:.0f} Cr"

def compute_fg(advances,declines,avg_del,fii):
    total=advances+declines
    b=((advances/total)*100) if total else 50; d=min(avg_del,100); fi=50
    if fii:
        try:
            net=float(str(fii['fii_net']).replace(',',''))
            fi=70 if net>2000 else (60 if net>0 else (35 if net>-2000 else 20))
        except: pass
    score=max(0,min(100,int(b*0.5+d*0.3+fi*0.2)))
    if score>=75: return score,"EXTREME GREED","#ff2222"
    if score>=55: return score,"GREED","#ff8800"
    if score>=45: return score,"NEUTRAL","#888888"
    if score>=25: return score,"FEAR","#4488ff"
    return score,"EXTREME FEAR","#0088ff"

def fii_signal(fii):
    if not fii: return "NO DATA","#555"
    try:
        net=float(str(fii['fii_net']).replace(',',''))
        if net>3000: return "HEAVY BUY","#00cc44"
        if net>500: return "NET BUY","#00cc44"
        if net>-500: return "NEUTRAL","#888"
        if net>-3000: return "NET SELL","#ff9944"
        return "HEAVY SELL","#ff3333"
    except: return "NO DATA","#555"

def sector_signal(sectors):
    if not sectors: return "NO DATA","#555"
    up={k:v for k,v in sectors.items() if v>0}; down={k:v for k,v in sectors.items() if v<0}
    if 'IT' in up and 'PHARMA' in up and len(down)>len(up): return "RISK-OFF MODE","#4488ff"
    if 'AUTO' in up and 'METALS' in up and 'BANKING' in up: return "RISK-ON MODE","#00cc44"
    if len(up)==0: return "CAPITULATION","#ff3333"
    if len(down)==0: return "STRONG BULL","#00cc44"
    return "MIXED MARKET","#ff9944"

def build(d, ticker_items):
    import json
    today=datetime.today().strftime('%d %b %Y').upper()
    ticker_html="".join(f'<span>{t}</span>' for t in ticker_items)*2

    pages=[("index.html","HOME"),("research.html","RESEARCH"),("market.html","MARKET"),("economy.html","ECONOMY")]
    links="".join(f'<a href="{u}" class="drawer-link{" active" if n=="MARKET" else ""}">{n}</a>' for u,n in pages)

    fii_sig,fii_sig_col=fii_signal(d['fii'])
    sec_sig,sec_sig_col=sector_signal(d['sectors'])
    fg_score,fg_label,fg_color=compute_fg(d['advances'],d['declines'],d['avg_delivery'],d['fii'])

    total_stocks=d['advances']+d['declines']+d['unchanged']
    ad_ratio=d['advances']/d['declines'] if d['declines'] else 0
    participation=(d['advances']/total_stocks*100) if total_stocks else 0
    if ad_ratio>=1.5: breadth_sig,breadth_col="BROAD RALLY","#00cc44"
    elif ad_ratio>=0.8: breadth_sig,breadth_col="SELECTIVE","#ff9944"
    else: breadth_sig,breadth_col="BROAD WEAKNESS","#ff3333"
    breadth_status_col="#00cc44" if ad_ratio>=1 else "#ff9944"
    breadth_status="POSITIVE" if ad_ratio>=1 else "NEGATIVE"

    n50=d['key_indices'].get('Nifty 50',{})
    ma=d['ma']
    tv_str=f"₹{ma['traded_val']:,.0f} Cr" if ma['traded_val'] else "--"
    mc_str=f"₹{ma['mktcap']/100000:.2f} L Cr" if ma['mktcap'] else "--"
    tr_str=f"{ma['trades']:,}" if ma['trades'] else "--"

    # JSON data for JS sorting
    gainers_json = json.dumps([{'name':g['name'],'pct':g['pct'],'price':g['price']} for g in d['gainers']])
    losers_json  = json.dumps([{'name':l['name'],'pct':l['pct'],'price':l['price']} for l in d['losers']])
    topval_json  = json.dumps([{'name':t['name'],'val_cr':t['val_cr'],'chg':t['chg'],'close':t['close']} for t in d['top_value']])
    bulk_json    = json.dumps([{'sym':b['sym'],'client':b['client'],'bs':b['bs'],'price':b['price'],'qty':b['qty']} for b in d['bulk']])
    short_json   = json.dumps([{'sym':s['sym'],'name':s['name'],'qty':s['qty']} for s in d['short']])
    deliv_json   = json.dumps([{'name':dv['name'],'pct':dv['pct']} for dv in d['delivery']])
    highs_json   = json.dumps([{'sym':h['sym'],'name':h['name']} for h in d['highs']])
    lows_json    = json.dumps([{'sym':l['sym'],'name':l['name']} for l in d['lows']])

    sector_rows_html=""
    sorted_sectors=sorted(d['sectors'].items(),key=lambda x:x[1],reverse=True)
    max_abs=max((abs(v) for _,v in sorted_sectors),default=1)
    for name,chg in sorted_sectors:
        bar_w=int(abs(chg)/max_abs*80)+8
        bar_col='#00cc44' if chg>0 else ('#ff9944' if abs(chg)<0.3 else '#ff3333')
        sector_rows_html+=f'<div class="sector-row"><span class="sector-name">{name}</span><div class="sector-bar-wrap"><div class="sector-bar" style="background:{bar_col};width:{bar_w}px;"></div></div><span class="sector-val" style="color:{cc(chg)}">{arr(chg)} {sg(chg)}{chg:.2f}%</span></div>'

    def fii_html(fii):
        if not fii: return '<div style="color:#333;font-size:10px;padding:12px 0;line-height:2.2;">Add <span style="color:#555;">fii_dii.csv</span> to market-data/<br>Cols: FII Buy, FII Sell, FII Net, DII Buy, DII Sell, DII Net</div>'
        def fc(v):
            try: return '#00cc44' if float(str(v).replace(',',''))>0 else '#ff3333'
            except: return '#888'
        try:
            fn=float(str(fii['fii_net']).replace(',','')); dn=float(str(fii['dii_net']).replace(',',''))
            comb=fn+dn; comb_col=cc(comb); comb_str=f"{sg(comb)}₹{abs(comb):,.0f} Cr"
            flow_l="NET INFLOW" if comb>=0 else "NET OUTFLOW"; flow_c='#00cc44' if comb>=0 else '#ff3333'
        except: comb_col='#888'; comb_str='--'; flow_l='--'; flow_c='#888'
        fsl,fsc=fii_signal(fii)
        return f"""<div class="data-row"><div><div class="data-lbl">FII NET</div><div class="data-sub">Buy ₹{fii['fii_buy']} Cr · Sell ₹{fii['fii_sell']} Cr</div></div><div class="data-val" style="color:{fc(fii['fii_net'])}">₹{fii['fii_net']} Cr</div></div>
        <div class="data-row"><div><div class="data-lbl">DII NET</div><div class="data-sub">Buy ₹{fii['dii_buy']} Cr · Sell ₹{fii['dii_sell']} Cr</div></div><div class="data-val" style="color:{fc(fii['dii_net'])}">₹{fii['dii_net']} Cr</div></div>
        <div class="data-row" style="border:none;"><div><div class="data-lbl">COMBINED NET</div><div class="data-sub">FII + DII total flow</div></div><div class="data-val" style="color:{comb_col}">{comb_str}</div></div>
        <div class="signal-box"><span class="signal-lbl">FII SIGNAL</span><span style="color:{fsc};font-weight:700;letter-spacing:2px;">{fsl}</span></div>
        <div class="signal-box"><span class="signal-lbl">MARKET FLOW</span><span style="color:{flow_c};font-weight:700;letter-spacing:2px;">{flow_l}</span></div>"""

    def index_cards():
        show=[('Nifty 50','NIFTY 50'),('Nifty Bank','BANK NIFTY'),('Nifty IT','NIFTY IT'),
              ('Nifty Pharma','PHARMA'),('NIFTY MIDCAP 100','MIDCAP 100'),('Nifty Next 50','NEXT 50')]
        html=""
        for key,label in show:
            idx=d['key_indices'].get(key,{})
            if not idx:
                html+=f'<div class="idx-card"><div class="idx-name">{label}</div><div class="idx-val">--</div><div class="idx-chg grey">N/A</div></div>'
            else:
                c=cc(idx['chg'])
                html+=f'<div class="idx-card"><div class="idx-name">{label}</div><div class="idx-val">{idx["close"]:,.2f}</div><div class="idx-chg" style="color:{c}">{arr(idx["chg"])} {sg(idx["chg"])}{idx["chg"]:.2f}%</div></div>'
        return html

    n50_close=n50.get('close',0); n50_chg=n50.get('chg',0)
    n50_high=n50.get('high',0); n50_low=n50.get('low',0)
    n50_prev=n50.get('prev',0); n50_hi52=n50.get('hi52','--'); n50_lo52=n50.get('lo52','--')

    CSS="""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'IBM Plex Mono',monospace;background:#000;color:#fff;font-size:12px;line-height:1.4;padding-bottom:40px}
#site-header{background:#000;border-bottom:2px solid #ff6600;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
#site-logo{font-size:1.6em;font-weight:700;color:#fff;letter-spacing:3px}
#nav-drawer{position:fixed;top:0;right:-260px;width:240px;height:100vh;background:#050505;border-left:1px solid #1a1a1a;z-index:999;padding:20px 0;transition:right .25s ease}
#nav-drawer.open{right:0}
#nav-drawer-header{display:flex;justify-content:space-between;align-items:center;padding:0 20px 16px;border-bottom:1px solid #1a1a1a;margin-bottom:10px}
.drawer-link{display:block;padding:14px 20px;color:#555;text-decoration:none;font-size:.80em;font-weight:700;letter-spacing:3px;border-bottom:1px solid #0f0f0f}
.drawer-link:hover{color:#fff;background:#0a0a0a}
.drawer-link.active{color:#ff6600}
#nav-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.6);z-index:998}
#nav-overlay.open{display:block}
#ticker-bar{background:#fff;color:#000;font-size:.75em;font-weight:700;padding:5px 0;overflow:hidden;white-space:nowrap;border-bottom:1px solid #ddd}
#ticker-content{display:inline-block;animation:scroll-ticker 90s linear infinite;padding-left:100%}
#ticker-content span{margin-right:60px;color:#000}
@keyframes scroll-ticker{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}
#status-bar{background:#0a0a0a;border-bottom:1px solid #111;padding:6px 24px;display:flex;gap:24px;align-items:center;font-size:0.68em;letter-spacing:1px;overflow-x:auto;white-space:nowrap}
.st-item{display:flex;gap:8px;align-items:center}
.st-lbl{color:#444}
#main-content{max-width:1200px;margin:0 auto;padding:16px 20px}
.section-head{font-size:0.65em;letter-spacing:3px;color:#444;border-bottom:1px solid #1a1a1a;padding-bottom:6px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
.section-badge{font-size:0.9em;padding:1px 8px;border:1px solid #1a1a1a;color:#333}
.sort-btns{display:flex;gap:4px}
.sort-btn{font-size:9px;padding:2px 8px;border:1px solid #222;background:none;color:#444;cursor:pointer;font-family:inherit;letter-spacing:1px}
.sort-btn.active,.sort-btn:hover{border-color:#ff6600;color:#ff6600}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#111;margin-bottom:1px}
.grid-2-1{display:grid;grid-template-columns:2fr 1fr;gap:1px;background:#111;margin-bottom:1px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#111;margin-bottom:1px}
.grid-6{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:#111;margin-bottom:1px}
.card{background:#000;padding:14px 16px}
.data-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #0d0d0d}
.data-lbl{color:#555;font-size:0.78em;letter-spacing:1px}
.data-val{font-size:0.9em;font-weight:700}
.data-sub{color:#333;font-size:0.65em;margin-top:2px}
.signal-box{margin-top:8px;padding:7px 12px;border:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center;background:#080808}
.signal-lbl{color:#333;font-size:0.65em;letter-spacing:2px}
.breadth-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:#111;margin:10px 0}
.breadth-cell{background:#080808;padding:10px 8px;text-align:center}
.breadth-num{font-size:1.8em;font-weight:700;line-height:1}
.breadth-lbl{font-size:0.6em;color:#333;letter-spacing:2px;margin-top:4px}
.fg-score{font-size:3.2em;font-weight:700;line-height:1;margin:6px 0 3px 0}
.fg-label{font-size:0.75em;letter-spacing:3px;font-weight:700}
.gauge-bar{width:100%;height:12px;background:linear-gradient(to right,#0044ff 0%,#0088ff 20%,#666 40%,#666 60%,#ff8800 80%,#ff2222 100%);border-radius:6px;position:relative;margin:12px 0 4px 0}
.gauge-needle{position:absolute;top:-5px;width:2px;height:22px;background:#fff;border-radius:1px;transform:translateX(-50%)}
.gauge-labels{display:flex;justify-content:space-between;font-size:0.6em;color:#333;letter-spacing:1px}
.sector-row{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #080808}
.sector-name{color:#888;font-size:0.75em;width:80px}
.sector-bar-wrap{flex:1;background:#0a0a0a;height:6px;border-radius:2px;overflow:hidden}
.sector-bar{height:6px;border-radius:2px}
.sector-val{font-size:0.75em;width:62px;text-align:right}
.data-table{width:100%;border-collapse:collapse}
.data-table th{font-size:0.6em;letter-spacing:2px;color:#333;text-align:left;padding:4px 6px;border-bottom:1px solid #111;font-weight:normal;cursor:pointer}
.data-table th:hover{color:#ff6600}
.data-table th.sorted{color:#ff6600}
.data-table td{font-size:0.82em;padding:5px 6px;border-bottom:1px solid #080808}
.data-table tr:hover td{background:#0a0a0a}
.up{color:#00cc44}.down{color:#ff3333}.orange{color:#ff6600}.grey{color:#555}
.hint{margin-top:8px;padding:5px 8px;background:#060606;font-size:0.65em;color:#2a2a2a;line-height:1.7;border-left:2px solid #111}
.blink{animation:blink 1.5s step-end infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.2}}
.scroll-box{max-height:200px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#1a1a1a #000}
.scroll-box::-webkit-scrollbar{width:3px}
.scroll-box::-webkit-scrollbar-track{background:#000}
.scroll-box::-webkit-scrollbar-thumb{background:#1a1a1a;border-radius:2px}
.expand-btn{width:100%;background:none;border:none;border-top:1px solid #111;color:#333;font-size:9px;letter-spacing:2px;padding:6px;cursor:pointer;font-family:inherit;text-align:center;margin-top:4px}
.expand-btn:hover{color:#ff6600;border-color:#ff6600}
.tag-list{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:4px;padding-bottom:4px;scrollbar-width:thin;scrollbar-color:#1a1a1a #000}
.tag-list::-webkit-scrollbar{height:3px}
.tag-list::-webkit-scrollbar-thumb{background:#1a1a1a}
.tag{font-size:0.62em;padding:4px 8px;white-space:nowrap;cursor:default}
.tag-h{background:#0a1f0a;color:#00cc44;border:1px solid #1a3a1a}
.tag-l{background:#1f0a0a;color:#ff3333;border:1px solid #3a1a1a}
.tag-sym{font-weight:700;margin-right:2px}
.tag-name{opacity:0.6}
.deliv-row{display:flex;align-items:center;padding:4px 0;border-bottom:1px solid #0a0a0a;gap:6px;font-size:10px}
.deliv-name{color:#888;font-size:9px;min-width:80px}
.deliv-bar-bg{background:#111;height:4px;flex:1;border-radius:2px}
.deliv-bar-fill{height:4px;border-radius:2px}
.idx-card{background:#000;padding:12px 14px;text-align:center}
.idx-name{font-size:0.58em;color:#444;letter-spacing:2px;margin-bottom:4px}
.idx-val{font-size:1.1em;font-weight:700;color:#fff}
.idx-chg{font-size:0.68em;font-weight:700;margin-top:2px}
.totals-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#111;margin-bottom:1px}
.total-cell{background:#000;padding:12px 18px}
.total-lbl{font-size:0.58em;color:#444;letter-spacing:2px;margin-bottom:5px}
.total-val{font-size:1.05em;font-weight:700;color:#ff6600}
#bookmark-panel{position:fixed;top:60px;right:20px;width:265px;max-height:400px;background:#0a0a0a;border:1px solid #1a1a1a;padding:14px;overflow-y:auto;display:none;z-index:999}
#bookmark-panel h3{color:#ff6600;letter-spacing:3px;font-size:.70em;border-bottom:1px solid #1a1a1a;padding-bottom:8px;margin-bottom:10px}
#footer{background:#000;border-top:1px solid #0a0a0a;padding:8px 24px;display:flex;justify-content:space-between;font-size:0.65em;color:#222;letter-spacing:1px;margin-top:2px}
@media(max-width:700px){.grid-3,.grid-2-1,.grid-6{grid-template-columns:1fr}.grid-2{grid-template-columns:1fr}.totals-grid{grid-template-columns:1fr 1fr}}
"""

    JS=f"""
const GAINERS={gainers_json};
const LOSERS={losers_json};
const TOPVAL={topval_json};
const BULK={bulk_json};
const SHORT={short_json};
const DELIVERY={deliv_json};
const HIGHS={highs_json};
const LOWS={lows_json};

function cc(v){{return v>0?'#00cc44':(v<0?'#ff3333':'#888')}}
function arr(v){{return v>=0?'▲':'▼'}}
function sg(v){{return v>=0?'+':''}}
function fcr(v){{return v>=1000?'₹'+(v/100).toFixed(1)+'K Cr':'₹'+v.toFixed(0)+' Cr'}}
function toggleMenu(){{document.getElementById('nav-drawer').classList.toggle('open');document.getElementById('nav-overlay').classList.toggle('open')}}
function togglePanel(){{const p=document.getElementById('bookmark-panel');p.style.display=p.style.display==='none'?'block':'none'}}

// Expand/collapse scroll box
function toggleExpand(id,btn){{
  const box=document.getElementById(id);
  if(box.style.maxHeight==='none'){{
    box.style.maxHeight='200px'; btn.textContent='▼ SHOW MORE';
  }}else{{
    box.style.maxHeight='none'; btn.textContent='▲ SHOW LESS';
  }}
}}

// Sort table
function sortTable(arr,key,asc){{
  return [...arr].sort((a,b)=>asc?(a[key]-b[key]):(b[key]-a[key]));
}}

// Render gainers
function renderGainers(sortKey='pct',asc=false){{
  const data=sortTable(GAINERS,sortKey,asc);
  document.getElementById('gainers-body').innerHTML=data.map(s=>
    `<tr><td style="color:#00cc44;font-weight:700;">${{s.name}}</td><td class="grey">₹${{s.price.toFixed(1)}}</td><td style="color:#00cc44;font-weight:700;">▲ +${{s.pct.toFixed(2)}}%</td></tr>`
  ).join('');
  document.querySelectorAll('#gainers-head th').forEach(th=>th.classList.remove('sorted'));
  document.getElementById('g-sort-'+sortKey).classList.add('sorted');
}}

// Render losers
function renderLosers(sortKey='pct',asc=true){{
  const data=sortTable(LOSERS,sortKey,asc);
  document.getElementById('losers-body').innerHTML=data.map(s=>
    `<tr><td style="color:#ff3333;font-weight:700;">${{s.name}}</td><td class="grey">₹${{s.price.toFixed(1)}}</td><td style="color:#ff3333;font-weight:700;">▼ ${{s.pct.toFixed(2)}}%</td></tr>`
  ).join('');
  document.querySelectorAll('#losers-head th').forEach(th=>th.classList.remove('sorted'));
  document.getElementById('l-sort-'+sortKey).classList.add('sorted');
}}

// Render top value
function renderTopVal(sortKey='val_cr',asc=false){{
  const data=sortTable(TOPVAL,sortKey,asc);
  document.getElementById('topval-body').innerHTML=data.map(s=>
    `<tr><td style="color:#ccc;font-weight:700;">${{s.name}}</td><td class="orange">${{fcr(s.val_cr)}}</td><td style="color:${{cc(s.chg)}};font-weight:700;">${{arr(s.chg)}} ${{sg(s.chg)}}${{s.chg.toFixed(2)}}%</td><td class="grey">₹${{s.close.toFixed(1)}}</td></tr>`
  ).join('');
}}

// Render bulk
function renderBulk(sortKey='sym',asc=true){{
  let data=[...BULK];
  if(sortKey==='bs') data.sort((a,b)=>asc?a.bs.localeCompare(b.bs):b.bs.localeCompare(a.bs));
  else if(sortKey==='price') data.sort((a,b)=>asc?parseFloat(a.price||0)-parseFloat(b.price||0):parseFloat(b.price||0)-parseFloat(a.price||0));
  else data.sort((a,b)=>asc?a.sym.localeCompare(b.sym):b.sym.localeCompare(a.sym));
  document.getElementById('bulk-body').innerHTML=data.map(b=>
    `<tr><td style="font-weight:700;color:#fff;">${{b.sym}}</td><td class="${{b.bs.toLowerCase().includes('buy')?'up':'down'}}" style="font-weight:700;">${{b.bs}}</td><td class="grey" style="font-size:0.8em;">${{b.client.substring(0,22)}}</td><td class="grey">₹${{b.price}}</td></tr>`
  ).join('');
}}

// Render short
function renderShort(sortKey='qty',asc=false){{
  const data=[...SHORT].sort((a,b)=>asc?parseInt(a.qty.replace(/,/g,''))-parseInt(b.qty.replace(/,/g,'')):parseInt(b.qty.replace(/,/g,''))-parseInt(a.qty.replace(/,/g,'')));
  document.getElementById('short-body').innerHTML=data.map(s=>
    `<div class="data-row"><div><span style="color:#ff9944;font-weight:700;">${{s.sym}}</span><div style="color:#444;font-size:9px;margin-top:2px;">${{s.name.substring(0,28)}}</div></div><span class="grey">${{s.qty}} qty</span></div>`
  ).join('');
}}

// Render delivery
function renderDelivery(sortKey='pct',asc=false){{
  const data=sortTable(DELIVERY,sortKey,asc);
  document.getElementById('delivery-body').innerHTML=data.map(s=>{{
    const pct=Math.min(s.pct,100); const bc=pct>=50?'#00cc44':(pct>=30?'#ff9944':'#ff3333');
    return `<div class="deliv-row"><span class="deliv-name">${{s.name.substring(0,16)}}</span><div class="deliv-bar-bg"><div class="deliv-bar-fill" style="background:${{bc}};width:${{Math.round(pct*0.6)}}px;"></div></div><span style="color:${{bc}};font-weight:700;">${{s.pct.toFixed(1)}}%</span></div>`;
  }}).join('');
}}

// Render 52W tags
function render52W(){{
  document.getElementById('highs-list').innerHTML=HIGHS.map(h=>
    `<span class="tag tag-h"><span class="tag-sym">${{h.sym}}</span><span class="tag-name">${{h.name.substring(0,18)}}</span></span>`
  ).join('');
  document.getElementById('lows-list').innerHTML=LOWS.map(l=>
    `<span class="tag tag-l"><span class="tag-sym">${{l.sym}}</span><span class="tag-name">${{l.name.substring(0,18)}}</span></span>`
  ).join('');
}}

window.onload=function(){{
  renderGainers(); renderLosers(); renderTopVal(); renderBulk(); renderShort(); renderDelivery(); render52W();
  let bm=JSON.parse(localStorage.getItem('bookmarks')||'[]');
  document.getElementById('bookmark-list').innerHTML=bm.length===0?'<li style="color:#333;cursor:default">No saved reports</li>':bm.map(b=>`<li>${{b}}</li>`).join('');
}}
"""

    html=f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{WEBSITE_TITLE} — Market Pulse</title>
<style>{CSS}</style>
</head>
<body>
<div id="site-header">
    <div id="site-logo">{WEBSITE_TITLE}</div>
    <button onclick="toggleMenu()" style="background:none;border:none;cursor:pointer;color:#888;font-size:1.4em;padding:0;line-height:1;">&#9776;</button>
</div>
<div id="nav-drawer">
    <div id="nav-drawer-header">
        <span style="color:#ff6600;font-size:0.75em;letter-spacing:3px;font-weight:700;">MENU</span>
        <button onclick="toggleMenu()" style="background:none;border:none;color:#444;cursor:pointer;font-size:1.2em;">&#10005;</button>
    </div>
    <nav>{links}<a href="#" class="drawer-link" onclick="togglePanel();toggleMenu();">SAVED</a></nav>
</div>
<div id="nav-overlay" onclick="toggleMenu()"></div>
<div id="ticker-bar"><div id="ticker-content">{ticker_html}</div></div>
<div id="status-bar">
    <div class="st-item"><span class="st-lbl">FII</span><span style="color:{fii_sig_col};font-weight:700;">{fii_sig}</span></div>
    <div class="st-item"><span class="st-lbl">BREADTH</span><span style="color:{breadth_status_col};font-weight:700;">{breadth_status}</span></div>
    <div class="st-item"><span class="st-lbl">SENTIMENT</span><span style="color:{fg_color};font-weight:700;">{fg_label}</span></div>
    <div class="st-item"><span class="st-lbl">SCORE</span><span style="color:{fg_color};font-weight:700;">{fg_score}/100</span></div>
    <div class="st-item"><span class="st-lbl">SECTOR</span><span style="color:{sec_sig_col};font-weight:700;">{sec_sig}</span></div>
    <div class="st-item" style="margin-left:auto;"><span class="orange blink">■</span>&nbsp;<span class="grey">EOD DATA · {today}</span></div>
</div>
<div id="main-content">
<div class="grid-6">{index_cards()}</div>
<div class="totals-grid">
    <div class="total-cell"><div class="total-lbl">TRADED VALUE</div><div class="total-val">{tv_str}</div></div>
    <div class="total-cell"><div class="total-lbl">MARKET CAP</div><div class="total-val">{mc_str}</div></div>
    <div class="total-cell"><div class="total-lbl">TOTAL TRADES</div><div class="total-val">{tr_str}</div></div>
    <div class="total-cell"><div class="total-lbl">AVG DELIVERY</div><div class="total-val">{d['avg_delivery']:.1f}%</div></div>
</div>
<!-- ROW 1 -->
<div class="grid-3">
    <div class="card">
        <div class="section-head">SMART MONEY TRACKER <span class="badge">FII / DII</span></div>
        {fii_html(d['fii'])}
    </div>
    <div class="card">
        <div class="section-head">INDIA FEAR &amp; GREED <span class="badge">QUANTIS</span></div>
        <div style="text-align:center;padding:8px 0;">
            <div class="fg-score" style="color:{fg_color};">{fg_score}</div>
            <div class="fg-label" style="color:{fg_color};">{fg_label}</div>
            <div class="gauge-bar"><div class="gauge-needle" style="left:{fg_score}%;"></div></div>
            <div class="gauge-labels"><span>EXT FEAR</span><span>FEAR</span><span>NEUTRAL</span><span>GREED</span><span>EXT GREED</span></div>
        </div>
        <div style="margin-top:12px;border-top:1px solid #111;padding-top:10px;">
            <div class="data-row"><span class="data-lbl">A/D RATIO</span><span style="color:#ff9944;font-weight:700;">{ad_ratio:.2f}</span></div>
            <div class="data-row"><span class="data-lbl">PARTICIPATION</span><span class="grey">{participation:.1f}%</span></div>
            <div class="data-row" style="border:none;"><span class="data-lbl">DELIVERY AVG</span><span class="grey">{d['avg_delivery']:.1f}%</span></div>
        </div>
    </div>
    <div class="card">
        <div class="section-head">RALLY HEALTH METER <span class="badge">BREADTH</span></div>
        <div class="breadth-grid">
            <div class="breadth-cell"><div class="breadth-num up">{d['advances']:,}</div><div class="breadth-lbl">ADVANCES</div></div>
            <div class="breadth-cell"><div class="breadth-num down">{d['declines']:,}</div><div class="breadth-lbl">DECLINES</div></div>
            <div class="breadth-cell"><div class="breadth-num grey">{d['unchanged']}</div><div class="breadth-lbl">UNCHANGED</div></div>
        </div>
        <div class="data-row"><span class="data-lbl">A/D RATIO</span><span style="color:#ff9944;font-weight:700;">{ad_ratio:.2f}</span></div>
        <div class="data-row"><span class="data-lbl">PARTICIPATION</span><span class="grey">{participation:.1f}%</span></div>
        <div class="data-row" style="border:none;"><span class="data-lbl">BREADTH SIGNAL</span><span style="color:{breadth_col};font-weight:700;">{breadth_sig}</span></div>
        <div class="signal-box" style="margin-top:10px;"><span class="signal-lbl">INTERPRETATION</span><span style="color:{breadth_col};font-weight:700;font-size:0.82em;">{breadth_sig}</span></div>
        <div class="hint">A/D &gt; 1.5 = broad rally · A/D &lt; 0.8 = broad weakness</div>
    </div>
</div>
<!-- ROW 2 -->
<div class="grid-2-1">
    <div class="card">
        <div class="section-head">SECTOR ROTATION MAP <span class="badge">NIFTY INDICES</span></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div>{sector_rows_html}</div>
            <div>
                <div style="font-size:0.65em;color:#444;letter-spacing:2px;margin-bottom:8px;">SIGNAL GUIDE</div>
                <div style="font-size:0.72em;color:#333;line-height:2.1;">IT + Pharma up = RISK-OFF<br>Auto + Metal up = RISK-ON<br>Banking up = liquidity +ve<br>All down = capitulation<br>All up = strong bull</div>
                <div class="signal-box" style="margin-top:14px;"><span class="signal-lbl">TODAY</span><span style="color:{sec_sig_col};font-weight:700;font-size:0.82em;">{sec_sig}</span></div>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="section-head">DELIVERY QUALITY <span class="badge">MTO</span>
            <div class="sort-btns">
                <button class="sort-btn active" onclick="renderDelivery('pct',false);setSortActive(this)">% HIGH</button>
                <button class="sort-btn" onclick="renderDelivery('pct',true);setSortActive(this)">% LOW</button>
            </div>
        </div>
        <div style="font-size:2em;font-weight:700;color:#ff9944;margin:4px 0 2px;">{d['avg_delivery']:.1f}%</div>
        <div style="font-size:0.65em;color:#333;letter-spacing:2px;margin-bottom:10px;">AVG DELIVERY %</div>
        <div id="delivery-scroll" class="scroll-box"><div id="delivery-body"></div></div>
        <button class="expand-btn" onclick="toggleExpand('delivery-scroll',this)">▼ SHOW MORE</button>
        <div class="hint">50%+ genuine · 30-50% mixed · Below 30% = speculation</div>
    </div>
</div>
<!-- ROW 3: Gainers | Losers | Bulk -->
<div class="grid-3">
    <div class="card">
        <div class="section-head">TOP GAINERS <span class="badge">NSE 500</span>
            <div class="sort-btns">
                <button class="sort-btn active" id="g-sort-pct" onclick="renderGainers('pct',false)">CHG%</button>
                <button class="sort-btn" id="g-sort-price" onclick="renderGainers('price',false)">PRICE</button>
            </div>
        </div>
        <div id="gainers-scroll" class="scroll-box">
            <table class="data-table" style="width:100%">
                <thead id="gainers-head"><tr><th>SECURITY</th><th>PRICE</th><th>CHG%</th></tr></thead>
                <tbody id="gainers-body"></tbody>
            </table>
        </div>
        <button class="expand-btn" onclick="toggleExpand('gainers-scroll',this)">▼ SHOW MORE</button>
    </div>
    <div class="card">
        <div class="section-head">TOP LOSERS <span class="badge">NSE 500</span>
            <div class="sort-btns">
                <button class="sort-btn active" id="l-sort-pct" onclick="renderLosers('pct',true)">CHG%</button>
                <button class="sort-btn" id="l-sort-price" onclick="renderLosers('price',false)">PRICE</button>
            </div>
        </div>
        <div id="losers-scroll" class="scroll-box">
            <table class="data-table" style="width:100%">
                <thead id="losers-head"><tr><th>SECURITY</th><th>PRICE</th><th>CHG%</th></tr></thead>
                <tbody id="losers-body"></tbody>
            </table>
        </div>
        <button class="expand-btn" onclick="toggleExpand('losers-scroll',this)">▼ SHOW MORE</button>
    </div>
    <div class="card">
        <div class="section-head">BULK DEALS <span class="badge">SMART MONEY</span>
            <div class="sort-btns">
                <button class="sort-btn active" onclick="renderBulk('sym',true);setSortActive(this)">SYM</button>
                <button class="sort-btn" onclick="renderBulk('bs',true);setSortActive(this)">B/S</button>
                <button class="sort-btn" onclick="renderBulk('price',false);setSortActive(this)">PRICE</button>
            </div>
        </div>
        <div id="bulk-scroll" class="scroll-box">
            <table class="data-table" style="width:100%">
                <thead><tr><th>SYM</th><th>ACT</th><th>ENTITY</th><th>PRICE</th></tr></thead>
                <tbody id="bulk-body"></tbody>
            </table>
        </div>
        <button class="expand-btn" onclick="toggleExpand('bulk-scroll',this)">▼ SHOW MORE</button>
    </div>
</div>
<!-- ROW 4: Top Traded | Short Selling -->
<div class="grid-2">
    <div class="card">
        <div class="section-head">TOP BY TRADED VALUE <span class="badge">TT FILE</span>
            <div class="sort-btns">
                <button class="sort-btn active" onclick="renderTopVal('val_cr',false);setSortActive(this)">VALUE</button>
                <button class="sort-btn" onclick="renderTopVal('chg',false);setSortActive(this)">CHG%</button>
                <button class="sort-btn" onclick="renderTopVal('close',false);setSortActive(this)">PRICE</button>
            </div>
        </div>
        <div id="topval-scroll" class="scroll-box">
            <table class="data-table" style="width:100%">
                <thead><tr><th>SECURITY</th><th>VALUE</th><th>CHG%</th><th>CLOSE</th></tr></thead>
                <tbody id="topval-body"></tbody>
            </table>
        </div>
        <button class="expand-btn" onclick="toggleExpand('topval-scroll',this)">▼ SHOW MORE</button>
    </div>
    <div class="card">
        <div class="section-head">SHORT SELLING WATCH <span class="badge">F&amp;O</span>
            <div class="sort-btns">
                <button class="sort-btn active" onclick="renderShort('qty',false);setSortActive(this)">QTY</button>
                <button class="sort-btn" onclick="renderShort('sym',true);setSortActive(this)">SYM</button>
            </div>
        </div>
        <div id="short-scroll" class="scroll-box"><div id="short-body"></div></div>
        <button class="expand-btn" onclick="toggleExpand('short-scroll',this)">▼ SHOW MORE</button>
        <div class="hint">High short = potential squeeze · Monitor for reversal</div>
    </div>
</div>
<!-- ROW 5: 52W -->
<div class="grid-2">
    <div class="card">
        <div class="section-head">52 WEEK HIGH ▲ <span class="badge">EQ SERIES · {len(d['highs'])} STOCKS</span></div>
        <div id="highs-list" class="tag-list"></div>
    </div>
    <div class="card">
        <div class="section-head">52 WEEK LOW ▼ <span class="badge">EQ SERIES · {len(d['lows'])} STOCKS</span></div>
        <div id="lows-list" class="tag-list"></div>
    </div>
</div>
<!-- ROW 6: Nifty | Key Indices | Stats -->
<div class="grid-3">
    <div class="card">
        <div class="section-head">NIFTY 50 <span class="badge">EOD</span></div>
        <div style="font-size:1.8em;font-weight:700;color:#fff;margin:6px 0 4px;">{n50_close:,.2f}</div>
        <div style="font-size:0.74em;color:{cc(n50_chg)};margin-bottom:12px;">{arr(n50_chg)} {sg(n50_chg)}{n50_chg:.2f}%</div>
        <div class="data-row"><span class="data-lbl">DAY HIGH</span><span class="up">{n50_high:,.2f}</span></div>
        <div class="data-row"><span class="data-lbl">DAY LOW</span><span class="down">{n50_low:,.2f}</span></div>
        <div class="data-row"><span class="data-lbl">PREV CLOSE</span><span class="grey">{n50_prev:,.2f}</span></div>
        <div class="data-row"><span class="data-lbl">52W HIGH</span><span class="up">{n50_hi52}</span></div>
        <div class="data-row" style="border:none;"><span class="data-lbl">52W LOW</span><span class="down">{n50_lo52}</span></div>
    </div>
    <div class="card">
        <div class="section-head">KEY INDICES <span class="badge">MA FILE</span></div>
        {"".join(f'<div class="data-row"><span class="data-lbl">{k.replace("Nifty ","").replace("NIFTY ","").upper()}</span><span style="color:{cc(v["chg"])};font-weight:700;">{arr(v["chg"])} {sg(v["chg"])}{v["chg"]:.2f}%</span></div>' for k,v in list(d["key_indices"].items())[:8])}
    </div>
    <div class="card">
        <div class="section-head">MARKET STATS <span class="badge">MA FILE</span></div>
        <div class="data-row"><span class="data-lbl">TRADED VALUE</span><span class="orange">{tv_str}</span></div>
        <div class="data-row"><span class="data-lbl">MARKET CAP</span><span class="orange">{mc_str}</span></div>
        <div class="data-row"><span class="data-lbl">TOTAL TRADES</span><span class="grey">{tr_str}</span></div>
        <div class="data-row"><span class="data-lbl">ADV / DEC / UNC</span><span class="grey">{d['advances']} / {d['declines']} / {d['unchanged']}</span></div>
        <div class="data-row"><span class="data-lbl">AVG DELIVERY</span><span class="orange">{d['avg_delivery']:.1f}%</span></div>
        <div class="data-row" style="border:none;"><span class="data-lbl">52W H / L COUNT</span><span class="grey">{len(d['highs'])} / {len(d['lows'])}</span></div>
    </div>
</div>
</div>
<div id="bookmark-panel"><h3>SAVED REPORTS</h3><ul id="bookmark-list"></ul></div>
<div id="footer">
    <span>{WEBSITE_TITLE} MARKET PULSE &nbsp;·&nbsp; DATA: NSE INDIA &nbsp;·&nbsp; {today}</span>
    <span>For informational purposes only &nbsp;·&nbsp; Not investment advice</span>
</div>
<script>
function setSortActive(btn){{const p=btn.closest('.sort-btns');p.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');}}
{JS}
</script>
</body>
</html>"""

    with open("market.html","w",encoding="utf-8") as f:
        f.write(html)
    print("market.html ready!")

if not os.path.exists(MARKET_FOLDER):
    os.makedirs(MARKET_FOLDER); print(f"'{MARKET_FOLDER}' folder banaya!")

print("Parsing files...")
pr_zip=find_pr_zip(); ma_file=find_ma(); mto_f=find_mto(); short_f=find_short()
nifty500_names=get_nifty500_names(pr_zip)
print(f"  NSE 500 names loaded: {len(nifty500_names)}")
ma_data=parse_ma(ma_file)
key_idx,gainers,losers,highs,lows,top_val=parse_pr(pr_zip,nifty500_names)
delivery,avg_del,advances,declines,unch=parse_mto(mto_f)
bulk=parse_bulk(); short=parse_short(short_f); fii=parse_fii()

data={'ma':ma_data,'key_indices':key_idx,'sectors':ma_data['sectors'],
      'gainers':gainers,'losers':losers,'highs':highs,'lows':lows,
      'top_value':top_val,'delivery':delivery,'avg_delivery':avg_del,
      'advances':advances,'declines':declines,'unchanged':unch,
      'bulk':bulk,'short':short,'fii':fii}

print("Fetching ticker..."); ticker=fetch_ticker()
build(data,ticker); print("Done!")