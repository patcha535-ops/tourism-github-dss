#!/usr/bin/env python3
"""verify_decision.py -- checks every number quoted in Section 5 and in the abstract/discussion/conclusion of the DSS manuscript
against results_dss/results_decision.json (python verify_decision.py results_dss/results_decision.json)."""
import json
import sys

r = json.load(open(sys.argv[1]))
rows = []


def chk(label, paper, mine, dec=None, tol=None):
    ok = abs(paper - mine) <= (tol if tol is not None else 0.5 * 10 ** (-dec) + 1e-9)
    rows.append((ok, label, paper, mine))


def same(label, paper, mine):
    rows.append((sorted(paper) == sorted(mine), label, paper, mine))


T = r["typology"]
chk("Type A provinces", 5, T["A"]["n"], 0); chk("Type A visit share", 33.1, T["A"]["visit_share"], 1); chk("Type A receipt share", 71.7, T["A"]["receipt_share"], 1)
chk("Type B provinces", 8, T["B"]["n"], 0); chk("Type C provinces", 2, T["C"]["n"], 0); chk("Type D provinces", 62, T["D"]["n"], 0)
chk("Type D visit share", 54.7, T["D"]["visit_share"], 1); chk("Type D receipt share", 17.6, T["D"]["receipt_share"], 1)
same("Type C members", ["Chiang Rai", "Trat"], r["type_members"]["C"])
rows.append((all(p in r["type_members"]["B"] for p in ["Chiang Mai", "Phangnga", "Songkhla"]), "Chiang Mai, Phangnga, Songkhla are type B", True, True))
chk("Lever identity error (THB) < 1e-6", 0.0, r["lever_identity_max_abs_error_thb"], tol=1e-6)
L = r["lever_slope"]
chk("Composition lever positive in provinces", 69, L["n_positive"], 0); chk("Min foreign/Thai yield ratio", 0.80, L["min_ratio"], 2)
chk("Max foreign/Thai yield ratio", 4.30, L["max_ratio"], 2); chk("Median foreign/Thai yield ratio", 1.34, L["median_ratio"], 2)
K = r["risk"]
chk("Spearman PS vs risk", 0.05, K["spearman_ps_risk"], 2); chk("p-value PS vs risk", 0.67, K["spearman_ps_risk_p"], 2)
chk("CV min", 0.04, K["cv_min"], 2); chk("CV max", 0.38, K["cv_max"], 2); chk("CV median", 0.10, K["cv_median"], 2)
S = r["stability_vs_lambda0"]
chk("Spearman lambda=1 vs 0", 0.90, S["1.0"]["spearman"], 2); chk("Top-10 retained at lambda=1", 10, S["1.0"]["top10_retained"], 0)
chk("Spearman lambda=2 vs 0", 0.82, S["2.0"]["spearman"], 2); chk("Top-10 retained at lambda=2", 8, S["2.0"]["top10_retained"], 0)
R_ = r["robustness"]
same("Robust provinces", ["Bangkok", "Chon Buri", "Chiang Mai", "Krabi", "Phangnga", "Phuket", "Surat Thani", "Songkhla"], R_["robust"])
same("Conditional provinces", ["Trat", "Chiang Rai", "Rayong", "Chumphon"], R_["conditional"])
chk("Not prioritised count", 65, R_["counts"]["not prioritised"], 0)
same("Pareto-efficient provinces", ["Nonthaburi", "Songkhla", "Phuket"], r["pareto"]["members"])
rows.append((len(r["leader_path"]) == 1 and r["leader_path"][0]["province"] == "Phuket" and r["leader_path"][0]["lam_to"] >= 50.0, "Phuket first for every lambda in [0,50]", True, len(r["leader_path"])))
rows.append((r["leaders_on_frontier"] and r["leader_risk_nonincreasing"] and r["crossings_verified"], "Propositions 3-4 hold on the data", True, True))
cx = {(c["overtaken"], c["overtaker"]): c["lam"] for c in r["crossings"]}
for (a, b), v in {("Krabi", "Bangkok"): 0.03, ("Krabi", "Surat Thani"): 0.25, ("Phangnga", "Chon Buri"): 0.20, ("Krabi", "Chon Buri"): 0.79,
                  ("Chiang Mai", "Songkhla"): 0.34, ("Phangnga", "Songkhla"): 1.62, ("Krabi", "Songkhla"): 1.91}.items():
    chk(f"Threshold {b} overtakes {a}", v, cx[(a, b)], 2)
rows.append((r["candidates"]["lowest_risk"] == "Songkhla", "Songkhla has the lowest risk among candidates", "Songkhla", r["candidates"]["lowest_risk"]))
rows.append((r["top10"]["0.0"][1] == "Krabi", "Krabi ranked second at lambda=0", "Krabi", r["top10"]["0.0"][1]))
rows.append((r["top10"]["0.0"][1:5] != r["top10"]["2.0"][1:5], "Order of ranks 2-5 differs between lambda=0 and lambda=2", True, True))
P = r["persistence"]
chk("PS Spearman 2023 vs 2024", 0.992, P["ps_spearman"], 3); chk("PS Kendall", 0.945, P["ps_kendall"], 3); chk("Top-10 overlap", 10, P["top10_overlap"], 0)
chk("Provinces above 100 (2023)", 7, P["n_above100_2023"], 0); chk("Provinces above 100 (2024)", 7, P["n_above100_2024"], 0); chk("CV Spearman 2023 vs 2024", 0.48, P["cv_spearman"], 2)
chk("Aggregation: national weighted mean", 100.0, r["aggregation"]["national_weighted_mean"], tol=1e-9); chk("Aggregation: max regional gap", 0.0, r["aggregation"]["max_abs_region_gap"], tol=1e-9)
bad = [x for x in rows if not x[0]]
print(f"{len(rows) - len(bad)} of {len(rows)} quoted decision-analysis numbers reproduce")
for ok, lab, p, m in bad:
    print(f"  DIFFERS  {lab}: manuscript {p}  recomputed {m}")
