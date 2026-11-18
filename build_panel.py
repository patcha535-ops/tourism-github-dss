#!/usr/bin/env python3
"""
build_panel.py -- builds the balanced province x month panel of Section 11.1 from the three MOTS provincial workbooks
(2024 = B.E. 2567 revised, 2025 = B.E. 2568 revised, 2026 = B.E. 2569 Jan-Mar revised / Apr-Sep preliminary) and runs
the consistency checks reported in the manuscript.

    python build_panel.py mots2024.xlsx mots2025.xlsx mots2026.xlsx panel.csv [prov.csv]

Each monthly sheet has, for every province, current-year and previous-year values (24 numbers per row):
occupancy (cur, prev, chg), guests, visitors total, Thai, foreign, receipts total, Thai, foreign (each cur, prev, %chg).
The previous-year columns of the 2024 sheets provide calendar year 2023.  Province names are harmonised by row position
(two spellings differ between workbooks); regional subtotal and national rows are dropped.
"""
import csv
import re
import sys

import numpy as np
import openpyxl

SHEET = re.compile(r"^[^\s\-\d]+?(25\d\d)\(?[A-Za-z]*\)?$")          # monthly sheets; excludes the cumulative sheets
REGION_PREFIX = "\u0e20\u0e32\u0e04"                                 # region rows start with this prefix
TOTAL_ROW = "\u0e23\u0e27\u0e21\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14"   # national total row
FIELDS = ["occupancy", "guests", "visitors_total", "visitors_thai", "visitors_foreign", "receipts_total", "receipts_thai", "receipts_foreign"]
CUR = [0, 3, 6, 9, 12, 15, 18, 21]
PREV = [1, 4, 7, 10, 13, 16, 19, 22]


def read_workbook(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for name in [s for s in wb.sheetnames if SHEET.match(s)]:
        rows = []
        for r in wb[name].iter_rows(values_only=True):
            if len(r) > 1 and isinstance(r[1], str):
                nums = [x for x in r[2:] if isinstance(x, (int, float))]
                if len(nums) >= 24:
                    rows.append((r[1].strip(), nums[:24]))
        out.append(rows)
    return out                                                       # list over months of [(name, 24 numbers)]


def split(rows):
    prov = [(n, v) for n, v in rows if not n.startswith(REGION_PREFIX) and n != TOTAL_ROW]
    total = [v for n, v in rows if n == TOTAL_ROW][0]
    return prov, total


def main():
    f24, f25, f26, out = sys.argv[1:5]
    prov_csv = sys.argv[5] if len(sys.argv) > 5 else None
    books = {2024: read_workbook(f24), 2025: read_workbook(f25), 2026: read_workbook(f26)}
    assert [len(books[y]) for y in (2024, 2025, 2026)] == [12, 12, 9]
    canon = [n for n, _ in split(books[2026][0])[0]]                  # canonical spellings: latest workbook
    assert len(canon) == 77
    cur, prev, nat = {}, {}, {}
    for y, months in books.items():
        for m, rows in enumerate(months, start=1):
            prov, total = split(rows)
            assert len(prov) == 77
            diff = [(a[0], b) for a, b in zip(prov, canon) if a[0] != b]
            assert len(diff) <= 2, diff                              # only the two known spelling variants
            for (n, v), c in zip(prov, canon):
                cur[(c, y, m)] = np.array([v[i] for i in CUR], float)
                prev[(c, y - 1, m)] = np.array([v[i] for i in PREV], float)
            nat[(y, m)] = np.array([total[i] for i in CUR], float)
    # ---- panel: 2023 from the previous-year columns of the 2024 sheets; 2024-2026 from the current-year columns
    panel = {}
    for c in canon:
        for m in range(1, 13):
            panel[(c, 2023, m)] = prev[(c, 2023, m)]
        for y, nm in ((2024, 12), (2025, 12), (2026, 9)):
            for m in range(1, nm + 1):
                panel[(c, y, m)] = cur[(c, y, m)]
    months = [(2023, m) for m in range(1, 13)] + [(2024, m) for m in range(1, 13)] + [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 10)]
    assert len(months) == 45 and len(panel) == 77 * 45
    # ---- checks reported in Section 11.1
    print("provinces:", len(canon), "| months:", len(months), "| records:", len(panel), "| NaN:", sum(np.isnan(v).any() for v in panel.values()))
    bad = [k for k, v in panel.items() if abs(v[3] + v[4] - v[2]) > 1 or abs(v[6] + v[7] - v[5]) > 0.05]
    print("Thai+foreign != total visitors/receipts in", len(bad), "records")
    for (y1, y2) in ((2024, 2025), (2025, 2026)):                    # overlapping vintages
        # previous-year columns of the later workbook vs current-year columns of the earlier one
        n_all = n_same = 0
        for c in canon:
            for m in range(1, (12 if y2 == 2025 else 9) + 1):
                a, b = cur[(c, y1, m)], prev[(c, y1, m)]
                n_all += 1
                n_same += int(np.allclose(a, b, atol=1e-6))
        print(f"overlap {y1} sheets of the {y1} and {y2} workbooks: {n_same}/{n_all} identical province-month records")
    v24 = sum(panel[(c, 2024, m)] for c in canon for m in range(1, 13))
    print("2024 annual totals  visitors %.0f | foreign %.0f | receipts %.2f" % (v24[2], v24[4], v24[5]),
          "(published: 353556836 | 83178986 | 2924506.59)")
    d = sum(panel[(c, 2025, 1)] for c in canon) - nat[(2025, 1)]
    print("Jan 2025 provincial sums minus national total row (visitors, receipts):", d[2], round(d[5], 4))
    if prov_csv:
        ref = sorted(int(float(r["visitors_total"])) for r in csv.DictReader(open(prov_csv, encoding="utf-8")))
        mine = sorted(int(round(sum(panel[(c, 2024, m)][2] for m in range(1, 13)))) for c in canon)
        print("2024 annual visitors by province equal the compiled table (prov.csv) for all 77 provinces:", ref == mine)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["province", "month", "occupancy", "guests", "visitors_total", "visitors_foreign", "receipts_total"])
        for c in canon:
            for (y, m) in months:
                v = panel[(c, y, m)]
                w.writerow([c, f"{y}-{m:02d}", v[0], v[1], v[2], v[4], v[5]])
    print("wrote", out)


if __name__ == "__main__":
    main()
