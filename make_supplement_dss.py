#!/usr/bin/env python3
"""make_supplement_te.py -- writes supplementary_te.tex with all code reproduced inline, the run manifest and the claim-check output."""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = [("build_dataset.py", "Extracts the 77-province 2024 dataset from the compiled data tables and validates it against the published regional and national totals."),
         ("te_analysis.py", "Descriptive analysis: Punch Score, Gini, Theil and between-region decomposition, within-region bootstrap, visitor-composition decomposition, global and local Moran, Spearman correlations, robustness, tables and figures."),
         ("verify_claims.py", "Compares every number quoted in the descriptive sections of the manuscript with the recomputation."),
         ("build_panel.py", "Builds the balanced 77-province by 45-month panel from the three monthly Ministry of Tourism and Sports workbooks and reproduces the consistency checks."),
         ("te_decision.py", "Decision-analytic module (Section 5): aggregation and lever identity, lever typology, risk measure, risk-adjusted scores, Pareto frontier, leader path, rank-reversal thresholds, robustness classification and persistence of the inputs."),
         ("test_decision.py", "Numerical checks of Propositions 1-4 on random instances and of the decision results on the data."),
         ("verify_decision.py", "Compares every number quoted in Section 5, the abstract, the discussion and the conclusion with the decision-module output."),
         ("run_all_dss.sh", "Single command that reproduces everything.")]
esc = lambda s: s.replace("_", r"\_")
sha = lambda p: hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest()


def listing(p, cap):
    src = open(os.path.join(HERE, p), encoding="utf-8").read().rstrip("\n")
    return (f"\\subsection{{\\texttt{{{esc(p)}}}}}\n{cap}\\par\\smallskip\\noindent SHA-256: \\texttt{{{sha(p)}}}\\par\n"
            f"\\begin{{lstlisting}}[language=Python,caption={{{esc(p)}}}]\n{src}\n\\end{{lstlisting}}\n")


man = json.load(open(os.path.join(HERE, "results_te", "manifest.json")))
dman = json.load(open(os.path.join(HERE, "results_dss", "manifest.json")))
check = subprocess.run([sys.executable, "verify_claims.py", "results_te/results.json"], cwd=HERE, capture_output=True, text=True).stdout.strip()
check += "\n" + subprocess.run([sys.executable, "verify_decision.py", "results_dss/results_decision.json"], cwd=HERE, capture_output=True, text=True).stdout.strip()
tests = "\n".join(l for l in subprocess.run([sys.executable, "test_decision.py"], cwd=HERE, capture_output=True, text=True).stdout.splitlines() if l.startswith(("PASS", "FAIL")))
out = r"""\documentclass[10pt,a4paper]{article}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage[margin=2cm]{geometry}\usepackage{xcolor}\usepackage{listings}\usepackage{booktabs}
\usepackage[colorlinks=true,linkcolor=blue!50!black,urlcolor=blue!50!black]{hyperref}
\lstset{basicstyle=\ttfamily\scriptsize,numbers=left,numberstyle=\tiny\color{gray},breaklines=true,columns=fullflexible,keepspaces=true,frame=single,framerule=0.2pt,showstringspaces=false,tabsize=4,
  keywordstyle=\color{blue!60!black},commentstyle=\color{green!40!black}\itshape,stringstyle=\color{red!50!black}}
\title{Supplementary Material\\ \large Code and data construction for ``Decision Support for Provincial Tourism Yield Monitoring: A Punch Score Framework with Lever Diagnosis and Risk-Adjusted Prioritisation''}
\date{}
\begin{document}\maketitle
\section{Overview}
This file reproduces in full the code that generates every table, figure and number of the manuscript. Python $\ge3.10$ with \texttt{numpy}, \texttt{scipy}, \texttt{pandas} and \texttt{matplotlib}; \texttt{pdftotext} is used once to read the compiled data tables. Run \texttt{sh run\_all\_dss.sh data\_tourism\_2024.pdf} (about one minute); the optional first step that rebuilds \texttt{panel.csv} from the three monthly Ministry workbooks is described in that script.

\paragraph{Data.} \texttt{provinces\_2024.csv} (77 rows) contains, for each province, recorded visits and receipts (total, Thai, foreign), accommodation guests and occupancy (Ministry of Tourism and Sports revised workbook, 28 August 2025); rooms, length of stay and daily expenditure (Domestic Tourism Statistics 2024); GPP (NESDC); registered population and area (National Statistical Office); and province centroids (OCHA boundaries). \texttt{build\_dataset.py} checks that Thai plus foreign visits and receipts equal the totals, that provincial values reconcile with the published regional and national rows (visits, receipts, guests, rooms), and reports the GPP rounding discrepancy of THB 4 million. SHA-256 of \texttt{provinces\_2024.csv}: \texttt{""" + man["data_sha256"] + r"""}.

\paragraph{Run.} Identifier \texttt{""" + man["run_id"] + r"""}; seed """ + str(man["seed"]) + r"""; """ + f"{man['boot']:,}".replace(",", "{,}") + r""" bootstrap replications (resampling provinces within regions); """ + f"{man['perm']:,}".replace(",", "{,}") + r""" permutations for global and local Moran statistics; local classification stability over 20 independent permutation seeds.

\paragraph{Decision module.} \texttt{te\_decision.py} reads \texttt{provinces\_2024.csv} and \texttt{panel.csv} (SHA-256 of \texttt{panel.csv}: \texttt{""" + dman["panel_sha256"] + r"""}); province names in the two sources are matched through the 2024 annual visit totals, which are unique across provinces. Run identifier \texttt{""" + dman["run_id"] + r"""}. The module is deterministic (no random numbers).

\paragraph{Numerical tests of the propositions.}
\begin{lstlisting}[numbers=none]
""" + tests + r"""
\end{lstlisting}

\paragraph{Claim check.}
\begin{lstlisting}[numbers=none]
""" + check + r"""
\end{lstlisting}
Every table, figure and quoted number of the manuscript is produced or checked by this code.

\section{Source code}
""" + "\n".join(listing(f, d) for f, d in FILES) + r"""
\section{Run manifests}
\begin{lstlisting}[numbers=none]
""" + json.dumps(man, indent=2) + "\n" + json.dumps(dman, indent=2) + r"""
\end{lstlisting}
\end{document}
"""
open(os.path.join(HERE, "supplementary_dss.tex"), "w", encoding="utf-8").write(out)
print("wrote supplementary_dss.tex")
