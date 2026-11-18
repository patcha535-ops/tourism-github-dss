#!/bin/sh
# Reproduces every number, table and figure of the DSS manuscript (and of the Tourism Economics version).
# Usage: sh run_all_dss.sh data_tourism_2024.pdf
# Optional first step (needs the three monthly Ministry workbooks, not redistributed here):
#   python3 build_panel.py mots2024.xlsx mots2025.xlsx mots2026.xlsx panel.csv
set -e
python3 build_dataset.py "${1:-data_tourism_2024.pdf}" provinces_2024.csv
python3 te_analysis.py provinces_2024.csv --outdir results_te
python3 verify_claims.py results_te/results.json
python3 te_decision.py provinces_2024.csv panel.csv --outdir results_dss
python3 test_decision.py
python3 verify_decision.py results_dss/results_decision.json
