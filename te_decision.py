#!/usr/bin/env python3
"""
te_decision.py -- decision-analytic extension of the Punch Score assessment (Section 5 of the manuscript).

Inputs : provinces_2024.csv (77 provinces, 2024)  and  panel.csv (77 provinces x 45 months, MOTS workbooks)
Outputs: results_dss/results_decision.json, results_dss/tex/*.tex (tables), results_dss/fig/*.pdf, results_dss/manifest.json

    python te_decision.py provinces_2024.csv panel.csv --outdir results_dss

Everything is deterministic (no random numbers).
"""
import argparse
import hashlib
import json
import os
import platform
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats

LAMBDA_GRID = np.round(np.arange(0.0, 2.0 + 1e-9, 0.05), 10)      # risk-aversion grid used for the robustness classification
LAMBDA_SHOW = [0.0, 1.0, 2.0]                                       # columns of the priority table (lambda = 1 is the PSDF baseline)
ROBUST_SHARE, TOP_K = 0.90, 10


# ----------------------------------------------------------------------------- core definitions
def punch_score(R, V):
    return 100.0 * (R / R.sum()) / (V / V.sum())                    # Eq. (1)


def pct_rank(x):
    return (stats.rankdata(x) - 1.0) / (len(x) - 1.0)               # average ranks scaled to [0,1], as in the PSDF application


def adjusted_score(ps, r, lam):
    """Risk-adjusted Punch Score  S_i(lambda) = PS_i / (1 + lambda r_i)  (single-criterion instance of Z w / (1 + lambda R))."""
    return ps / (1.0 + lam * r)


def pareto_front(ps, r):
    """Indices not dominated by another province with PS >= and risk <= (at least one strict)."""
    n = len(ps)
    keep = []
    for i in range(n):
        dom = np.any((ps >= ps[i]) & (r <= r[i]) & ((ps > ps[i]) | (r < r[i])))
        if not dom:
            keep.append(i)
    return np.array(keep)


def crossing(ps_i, r_i, ps_j, r_j):
    """lambda at which S_i = S_j (None if no non-negative crossing): lambda* = (PS_j - PS_i) / (PS_i r_j - PS_j r_i)."""
    den = ps_i * r_j - ps_j * r_i
    if den == 0:
        return None
    lam = (ps_j - ps_i) / den
    return float(lam) if lam >= 0 else None


def leader_path(ps, r, lam_max=50.0, step=0.001):
    lam = np.arange(0.0, lam_max + step / 2, step)
    S = ps[None, :] / (1.0 + lam[:, None] * r[None, :])
    lead = S.argmax(1)
    path, start = [], 0
    for k in range(1, len(lam) + 1):
        if k == len(lam) or lead[k] != lead[start]:
            path.append((int(lead[start]), float(lam[start]), float(lam[k - 1]) if k < len(lam) else float(lam_max)))
            start = k
    return path


# ----------------------------------------------------------------------------- data
def load(prov_csv, panel_csv):
    df = pd.read_csv(prov_csv)
    pn = pd.read_csv(panel_csv)
    pn["year"] = pn.month.str[:4].astype(int)
    tot24 = pn[pn.year == 2024].groupby("province").visitors_total.sum()
    key = {int(round(v)): p for p, v in tot24.items()}
    assert len(key) == 77, "2024 annual visits must be unique across provinces to match the two sources"
    df["panel_name"] = [key[int(round(v))] for v in df.visits]
    assert df.panel_name.nunique() == 77
    def monthly(year):
        sub = pn[pn.year == year].pivot(index="province", columns="month", values="visitors_total")
        return sub.loc[df.panel_name].values
    def annual(year, col):
        return pn[pn.year == year].groupby("province")[col].sum().loc[df.panel_name].values
    return df, monthly(2024), monthly(2023), annual(2023, "visitors_total"), annual(2023, "receipts_total")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prov"); ap.add_argument("panel")
    ap.add_argument("--outdir", default="results_dss")
    a = ap.parse_args()
    os.makedirs(f"{a.outdir}/tex", exist_ok=True); os.makedirs(f"{a.outdir}/fig", exist_ok=True)
    df, m24, m23, V23, R23 = load(a.prov, a.panel)
    n = len(df)
    names = df.province.values
    R, V = df.receipts.values, df.visits.values
    ps = punch_score(R, V)
    res = {}

    # ---- Proposition 1: consistent aggregation of the Punch Score
    nat = float(np.sum(V / V.sum() * ps))
    reg_gap = 0.0
    for g in ["Bangkok", "Central", "East", "North", "Northeast", "South"]:
        m = (df.region == g).values
        direct = 100 * (R[m].sum() / R.sum()) / (V[m].sum() / V.sum())
        agg = float(np.sum(V[m] / V[m].sum() * ps[m]))
        reg_gap = max(reg_gap, abs(direct - agg))
    res["aggregation"] = dict(national_weighted_mean=nat, max_abs_region_gap=reg_gap)

    # ---- Proposition 2: lever identity and typology (Eq. 8 with 77-province national benchmarks)
    fT = df.visits_foreign.sum() / V.sum()
    yT = df.receipts_thai.sum() * 1e6 / df.visits_thai.sum()
    yF = df.receipts_foreign.sum() * 1e6 / df.visits_foreign.sum()
    y = R * 1e6 / V
    fi = df.visits_foreign.values / V
    comp = (fi - fT) * (yF - yT)
    within = (1 - fi) * (df.receipts_thai.values * 1e6 / df.visits_thai.values - yT) + fi * (df.receipts_foreign.values * 1e6 / df.visits_foreign.values - yF)
    ybar = R.sum() * 1e6 / V.sum()
    res["lever_identity_max_abs_error_thb"] = float(np.max(np.abs((y - ybar) - (comp + within))))
    yTi_ = df.receipts_thai.values * 1e6 / df.visits_thai.values
    yFi_ = df.receipts_foreign.values * 1e6 / df.visits_foreign.values
    slope = yFi_ - yTi_                                                   # d y_i / d f_i with provincial segment yields held fixed
    res["lever_slope"] = dict(n_positive=int((slope > 0).sum()), min_slope_thb=float(slope.min()), max_slope_thb=float(slope.max()),
                              min_ratio=float((yFi_ / yTi_).min()), max_ratio=float((yFi_ / yTi_).max()), median_ratio=float(np.median(yFi_ / yTi_)))
    typ = np.where(comp > 0, np.where(within > 0, "A", "B"), np.where(within > 0, "C", "D"))
    desc = {"A": "composition and within-type rates both above benchmark", "B": "composition above, within-type rates below",
            "C": "composition below, within-type rates above", "D": "composition and within-type rates both below"}
    rows, res["typology"] = [], {}
    for t in "ABCD":
        m = typ == t
        ex = list(df.province[m].iloc[np.argsort(-R[m])][:4])
        res["typology"][t] = dict(n=int(m.sum()), receipt_share=float(100 * R[m].sum() / R.sum()), visit_share=float(100 * V[m].sum() / V.sum()), examples=ex,
                                  mean_ps=float(ps[m].mean()) if m.any() else None)
        rows.append([t, desc[t], int(m.sum()), f"{100 * V[m].sum() / V.sum():.1f}", f"{100 * R[m].sum() / R.sum():.1f}", ", ".join(ex)])
    res["type_members"] = {t: list(df.province[typ == t]) for t in "ABCD"}
    tex_t = "\\begin{tabular}{llrrrp{5.2cm}}\n\\toprule\nType & Lever pattern & Provinces & Visits (\\%) & Receipts (\\%) & Largest provinces by receipts \\\\\n\\midrule\n" + "\n".join(" & ".join(map(str, r)) + " \\\\" for r in rows) + "\n\\bottomrule\n\\end{tabular}\n"
    open(f"{a.outdir}/tex/table_typology.tex", "w").write(tex_t)

    # ---- risk measure and risk-adjusted prioritisation (Propositions 3-4)
    cv24 = m24.std(axis=1, ddof=1) / m24.mean(axis=1)
    cv23 = m23.std(axis=1, ddof=1) / m23.mean(axis=1)
    r = pct_rank(cv24)
    res["risk"] = dict(cv_min=float(cv24.min()), cv_max=float(cv24.max()), cv_median=float(np.median(cv24)), spearman_ps_risk=float(stats.spearmanr(ps, r).statistic),
                       spearman_ps_risk_p=float(stats.spearmanr(ps, r).pvalue))
    S = {lam: adjusted_score(ps, r, lam) for lam in LAMBDA_GRID}
    rank = lambda s: (stats.rankdata(-s, method="min")).astype(int)
    rk = {lam: rank(S[lam]) for lam in LAMBDA_GRID}
    top = {lam: set(np.where(rk[lam] <= TOP_K)[0]) for lam in LAMBDA_GRID}
    stab = {}
    for lam in [0.25, 0.5, 1.0, 1.5, 2.0]:
        stab[str(lam)] = dict(spearman=float(stats.spearmanr(S[0.0], S[lam]).statistic), kendall=float(stats.kendalltau(S[0.0], S[lam]).statistic),
                              top10_retained=int(len(top[0.0] & top[lam])))
    res["stability_vs_lambda0"] = stab
    # robustness classification over the lambda grid
    share_top = np.array([np.mean([i in top[l] for l in LAMBDA_GRID]) for i in range(n)])
    cls = np.where(share_top >= ROBUST_SHARE, "robust", np.where(share_top > 0, "conditional", "not prioritised"))
    res["robustness"] = {c: list(names[cls == c][np.argsort(-share_top[cls == c])]) for c in ["robust", "conditional"]}
    res["robustness"]["counts"] = {c: int((cls == c).sum()) for c in ["robust", "conditional", "not prioritised"]}
    res["robustness"]["share_top10"] = {names[i]: float(share_top[i]) for i in range(n) if share_top[i] > 0}
    # priority table
    prow = []
    for k in range(TOP_K):
        row = [k + 1]
        for lam in LAMBDA_SHOW:
            i = int(np.argsort(-S[lam], kind="stable")[k])
            row += [names[i], f"{S[lam][i]:.1f}"]
        prow.append(row)
    tex_p = ("\\begin{tabular}{rllllll}\n\\toprule\n & \\multicolumn{2}{c}{$\\lambda=0$ (no risk adjustment)} & \\multicolumn{2}{c}{$\\lambda=1$ (baseline)} & \\multicolumn{2}{c}{$\\lambda=2$} \\\\\n"
             "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\nRank & Province & $S_i$ & Province & $S_i$ & Province & $S_i$ \\\\\n\\midrule\n"
             + "\n".join(" & ".join(map(str, r_)) + " \\\\" for r_ in prow) + "\n\\bottomrule\n\\end{tabular}\n")
    open(f"{a.outdir}/tex/table_priority.tex", "w").write(tex_p)
    res["top10"] = {str(l): [names[i] for i in np.argsort(-S[l], kind="stable")[:TOP_K]] for l in LAMBDA_SHOW}

    # ---- Pareto frontier and lambda regimes
    fr = pareto_front(ps, r)
    path = leader_path(ps, r)
    res["pareto"] = dict(n=int(len(fr)), members=[names[i] for i in fr[np.argsort(r[fr])]])
    res["leader_path"] = [dict(province=names[i], lam_from=lo, lam_to=hi) for i, lo, hi in path]
    brk = []
    for (i, lo, hi), (j, lo2, hi2) in zip(path[:-1], path[1:]):
        c = crossing(ps[i], r[i], ps[j], r[j])
        brk.append(dict(from_=names[i], to=names[j], lam_crossing=c, grid_switch=lo2))
    res["leader_breaks"] = brk
    in_front = {names[i] for i in fr}
    res["leaders_on_frontier"] = all(names[i] in in_front for i, _, _ in path)
    # monotone comparative statics: risk of the top-ranked province never rises with lambda
    risks_leader = [r[i] for i, _, _ in path]
    res["leader_risk_nonincreasing"] = bool(all(x >= y_ - 1e-12 for x, y_ in zip(risks_leader[:-1], risks_leader[1:])))
    fr_rows = []
    for i in fr[np.argsort(r[fr])]:
        segs = [(lo, hi) for (j, lo, hi) in path if j == i]
        lead = "; ".join(f"[{lo:.2f}, {hi:.2f}]" if hi < 50.0 else f"[{lo:.2f}, $\\infty$)" for lo, hi in segs) if segs else "--"
        fr_rows.append([names[i], f"{ps[i]:.1f}", f"{r[i]:.2f}", f"{cv24[i]:.3f}", lead])
    tex_f = ("\\begin{tabular}{lrrrl}\n\\toprule\nProvince & Punch Score & Risk $r_i$ & CV of monthly visits & Values of $\\lambda$ at which it ranks first \\\\\n\\midrule\n"
             + "\n".join(" & ".join(r_) + " \\\\" for r_ in fr_rows) + "\n\\bottomrule\n\\end{tabular}\n")
    open(f"{a.outdir}/tex/table_pareto.tex", "w").write(tex_f)

    # ---- rank-reversal thresholds among the provinces that matter for the top ten (Proposition 4)
    cand = sorted(set(np.where((rk[0.0] <= TOP_K + 2) | (rk[2.0] <= TOP_K + 2))[0]))
    cr = []
    for i in cand:
        for j in cand:
            if ps[i] > ps[j] and r[i] > r[j]:                                 # i yields more but is riskier: j may overtake i
                lam_star = crossing(ps[i], r[i], ps[j], r[j])
                if lam_star is not None and lam_star <= LAMBDA_GRID[-1]:
                    cr.append((lam_star, i, j))
    cr.sort()
    res["candidates"] = dict(names=[names[i] for i in cand], lowest_risk=names[cand[int(np.argmin(r[cand]))]])
    res["crossings"] = [dict(overtaken=names[i], overtaker=names[j], lam=float(l), ps_i=float(ps[i]), r_i=float(r[i]), ps_j=float(ps[j]), r_j=float(r[j])) for l, i, j in cr]
    # verify every crossing on the grid: order flips across lambda*
    ok = True
    for l, i, j in cr:
        lo, hi = max(l - 1e-6, 0.0), l + 1e-6
        ok &= bool(adjusted_score(ps[i], r[i], lo) >= adjusted_score(ps[j], r[j], lo) and adjusted_score(ps[i], r[i], hi) <= adjusted_score(ps[j], r[j], hi))
    res["crossings_verified"] = ok
    rows = [[names[i], names[j], f"{ps[i]:.1f} / {r[i]:.2f}", f"{ps[j]:.1f} / {r[j]:.2f}", f"{l:.2f}"] for l, i, j in cr[:12]]
    tex_c = ("\\begin{tabular}{llccr}\n\\toprule\nHigher-yield province & Overtaken by & $PS_i$ / $r_i$ & $PS_j$ / $r_j$ & Threshold $\\lambda^{*}_{ij}$ \\\\\n\\midrule\n"
             + "\n".join(" & ".join(r_) + " \\\\" for r_ in rows) + "\n\\bottomrule\n\\end{tabular}\n")
    open(f"{a.outdir}/tex/table_crossings.tex", "w").write(tex_c)

    # ---- temporal persistence (validation of the priority input)
    ps23 = punch_score(R23, V23)
    t10_24, t10_23 = set(np.argsort(-ps)[:10]), set(np.argsort(-ps23)[:10])
    sp = stats.spearmanr(ps23, ps); kt = stats.kendalltau(ps23, ps); sr = stats.spearmanr(cv23, cv24)
    res["persistence"] = dict(ps_spearman=float(sp.statistic), ps_spearman_p=float(sp.pvalue), ps_kendall=float(kt.statistic), top10_overlap=int(len(t10_24 & t10_23)),
                              n_above100_2023=int((ps23 > 100).sum()), n_above100_2024=int((ps > 100).sum()),
                              cv_spearman=float(sr.statistic), cv_spearman_p=float(sr.pvalue), ps23_median=float(np.median(ps23)))
    # same-set check: 2023 national totals
    res["persistence"]["receipts_2023_total_mTHB"] = float(R23.sum()); res["persistence"]["visits_2023_total"] = float(V23.sum())
    tex_v = ("\\begin{tabular}{lr}\n\\toprule\nStatistic & Value \\\\\n\\midrule\n"
             f"Spearman correlation, Punch Score 2023 vs 2024 & {sp.statistic:.3f} \\\\\n"
             f"Kendall's $\\tau$, Punch Score 2023 vs 2024 & {kt.statistic:.3f} \\\\\n"
             f"Provinces in the top ten in both years & {len(t10_24 & t10_23)} of 10 \\\\\n"
             f"Provinces above 100 in 2023 / 2024 & {int((ps23 > 100).sum())} / {int((ps > 100).sum())} \\\\\n"
             f"Spearman correlation, risk (CV of monthly visits) 2023 vs 2024 & {sr.statistic:.3f} \\\\\n"
             "\\bottomrule\n\\end{tabular}\n")
    open(f"{a.outdir}/tex/table_persistence.tex", "w").write(tex_v)

    # ---- appendix: full decision table
    o = np.argsort(-ps, kind="stable")
    rows = []
    for i in o:
        rows.append([names[i], df.region[i], f"{ps[i]:.1f}", f"{comp[i]:,.0f}".replace("-", "$-$"), f"{within[i]:,.0f}".replace("-", "$-$"), typ[i], f"{r[i]:.2f}",
                     int(rk[0.0][i]), int(rk[1.0][i]), int(rk[2.0][i]), f"{100 * share_top[i]:.0f}", cls[i]])
    hdr = "Province & Region & PS & Comp.\\ (THB) & Within (THB) & Type & $r_i$ & Rank $\\lambda{=}0$ & Rank $\\lambda{=}1$ & Rank $\\lambda{=}2$ & In top 10 (\\% of grid) & Class"
    body = "\n".join(" & ".join(map(str, r_)) + " \\\\" for r_ in rows)
    open(f"{a.outdir}/tex/table_decision_full.tex", "w").write(
        f"\\begin{{longtable}}{{llrrrcrrrrrl}}\n\\toprule\n{hdr} \\\\\n\\midrule\n\\endfirsthead\n\\toprule\n{hdr} \\\\\n\\midrule\n\\endhead\n\\bottomrule\n\\endfoot\n{body}\n\\end{{longtable}}\n")

    # ---- figures
    fig, ax = plt.subplots(figsize=(6.0, 4.6))
    ax.scatter(r, ps, s=22, c="lightgrey", edgecolor="grey", linewidth=0.4, zorder=2)
    ax.scatter(r[fr], ps[fr], s=48, c="#d7191c", edgecolor="k", linewidth=0.5, zorder=3, label="Pareto-efficient")
    o_fr = fr[np.argsort(r[fr])]
    ax.step(r[o_fr], ps[o_fr], where="post", color="#d7191c", linewidth=0.9, zorder=1)
    for i in list(o_fr) + [int(np.where(names == "Bangkok")[0][0]), int(np.where(names == "Chiang Mai")[0][0])]:
        ax.annotate(names[i], (r[i], ps[i]), fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.axhline(100, color="k", linestyle=":", linewidth=0.7)
    ax.set_yscale("log"); ax.set_xlabel(r"Risk $r_i$ (percentile rank of the CV of monthly visits, 2024)"); ax.set_ylabel("Punch Score (log scale)")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig(f"{a.outdir}/fig/fig4_risk_yield.pdf"); plt.close(fig)
    sel = sorted(set(np.where((rk[0.0] <= TOP_K) | (rk[2.0] <= TOP_K))[0]), key=lambda i: rk[0.0][i])
    fig, ax = plt.subplots(figsize=(6.0, 4.6))
    for i in sel:
        ax.plot(LAMBDA_GRID, [rk[l][i] for l in LAMBDA_GRID], linewidth=1.2)
        ax.annotate(names[i], (LAMBDA_GRID[-1], rk[LAMBDA_GRID[-1]][i]), fontsize=6.5, xytext=(3, 0), textcoords="offset points", va="center")
    ax.set_ylim(TOP_K + 4.5, 0.5); ax.axhline(TOP_K + 0.5, color="k", linestyle=":", linewidth=0.7)
    ax.set_xlim(0, LAMBDA_GRID[-1] * 1.28); ax.set_xlabel(r"Risk-aversion parameter $\lambda$"); ax.set_ylabel("Rank by risk-adjusted Punch Score")
    fig.tight_layout(); fig.savefig(f"{a.outdir}/fig/fig5_rank_paths.pdf"); plt.close(fig)

    json.dump(res, open(f"{a.outdir}/results_decision.json", "w"), indent=1, default=float)
    man = dict(prov_sha256=hashlib.sha256(open(a.prov, "rb").read()).hexdigest(), panel_sha256=hashlib.sha256(open(a.panel, "rb").read()).hexdigest(),
               code_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(), lambda_grid=[float(LAMBDA_GRID[0]), float(LAMBDA_GRID[-1]), float(LAMBDA_GRID[1] - LAMBDA_GRID[0])],
               top_k=TOP_K, robust_share=ROBUST_SHARE, python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__, pandas=pd.__version__, platform=platform.platform())
    man["run_id"] = hashlib.sha256((man["prov_sha256"] + man["panel_sha256"] + man["code_sha256"]).encode()).hexdigest()[:12]
    json.dump(man, open(f"{a.outdir}/manifest.json", "w"), indent=1)
    print("done", man["run_id"])


if __name__ == "__main__":
    main()
