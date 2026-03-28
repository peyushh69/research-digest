import xlrd
import sys

fp = r'c:\Users\Microsoft\Downloads\research-digest\market-data\daily\fii_stats_27-Mar-2026.xls'
try:
    wb = xlrd.open_workbook(fp)
    ws = wb.sheet_by_index(0)
    print(f"Sheet: {ws.name}, Rows: {ws.nrows}, Cols: {ws.ncols}")
    for r in range(min(10, ws.nrows)):
        row_cells = []
        for c in range(min(10, ws.ncols + 2)):
            try:
                val = ws.cell_value(r, c)
                row_cells.append(f"[{c}]:{val}")
            except:
                row_cells.append(f"[{c}]:OUT")
        print(f"Row {r}: {' | '.join(row_cells)}")
except Exception as e:
    print(f"Error: {e}")
