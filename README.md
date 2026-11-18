# Tourism yield in Thailand: descriptive assessment and decision-support framework (code, data, manuscript sources)

Code, derived data and LaTeX sources for two manuscript versions built on the same 2024 provincial data:

* **Decision Support version** (`main_dss.tex`): *Decision Support for Provincial Tourism Yield Monitoring: A Punch Score Framework with Lever Diagnosis and Risk-Adjusted Prioritisation* (adds the decision-analytic Section 5).
* **Descriptive version** (`main_te.tex`): *Tourism Yield and Spatial Concentration in Thailand: A Provincial Assessment Using the Punch Score*.

## Contents
| Path | What it is |
|---|---|
| `build_dataset.py` | Extracts the 77-province dataset from the compiled data tables (`data_tourism_2024.pdf`) and validates it against published totals |
| `te_analysis.py`, `verify_claims.py` | Descriptive analysis (Punch Score, concentration, decompositions, spatial statistics) and a check of 171 quoted numbers |
| `build_panel.py` | Builds the 77 x 45 monthly panel (`panel.csv`) from the three monthly Ministry workbooks (not redistributed) |
| `te_decision.py`, `test_decision.py`, `verify_decision.py` | Decision-analytic module (Section 5), numerical checks of Propositions 1-4, and a check of 48 quoted numbers |
| `run_all_dss.sh` | Reproduces everything |
| `provinces_2024.csv`, `panel.csv` | Derived data (see the data notice) |
| `results_te/`, `results_dss/` | Outputs the manuscripts are built from (tables, figures, JSON, manifests) |
| `main_dss.tex`, `title_page_dss.tex`, `cover_letter_dss.tex`, `supplementary_dss.tex` (+ PDFs) | Decision Support submission files |
| `main_te.tex`, `title_page.tex`, `supplementary_te.tex` (+ PDFs) | Descriptive version |

## Reproduce
```
pip install -r requirements.txt            # also needs the pdftotext command (poppler-utils)
sh run_all_dss.sh data_tourism_2024.pdf    # about one minute
python make_supplement_dss.py              # regenerates supplementary_dss.tex
pdflatex main_dss.tex && pdflatex main_dss.tex    # twice
```

## Data notice
Compiled from public sources: Ministry of Tourism and Sports (provincial tourism statistics, revised 28 August 2025; Domestic Tourism Statistics 2024; monthly provincial workbooks 2024-2026), NESDC (gross provincial product), National Statistical Office (registered population, area) and OCHA (province boundaries, used for centroids). Check each provider's terms of reuse before redistributing. The MIT licence covers the code only.

## Archiving / citing
Create a GitHub release with a tag that does not exist yet (this version: `v1.1.0`), let Zenodo archive it, and use the DOI of that release in the manuscript (`\RepoDOI` in `main_dss.tex`, `title_page_dss.tex` and `cover_letter_dss.tex`). Keep `version` in `CITATION.cff` equal to the tag.
