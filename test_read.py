import xlrd
fp = r'c:\Users\Microsoft\Downloads\research-digest\market-data\daily\fii_stats_27-Mar-2026.xls'
wb = xlrd.open_workbook(fp)
ws = wb.sheet_by_index(0)
print(f"File ok: {ws.nrows} rows")
for r in range(5):
    print(ws.row_values(r))
