"""Numerical checks of Propositions 1-4 (random instances) and of the decision results on the real data.  Run: python test_decision.py"""
import json
import subprocess
import sys

import numpy as np

import te_decision as D


def test_p1_aggregation_random():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n = rng.integers(3, 40)
        V, R = rng.uniform(1, 100, n), rng.uniform(1, 500, n)
        ps = D.punch_score(R, V)
        assert abs(np.sum(V / V.sum() * ps) - 100) < 1e-9                    # national mean is 100
        g = rng.random(n) < 0.5
        if g.any() and (~g).any():
            direct = 100 * (R[g].sum() / R.sum()) / (V[g].sum() / V.sum())
            assert abs(direct - np.sum(V[g] / V[g].sum() * ps[g])) < 1e-9     # group score = visit-weighted mean of member scores


def test_p2_lever_identity_random():
    rng = np.random.default_rng(2)
    for _ in range(200):
        n = 20
        VT, VF = rng.uniform(1, 100, n), rng.uniform(1, 100, n)
        RT, RF = VT * rng.uniform(1, 5, n), VF * rng.uniform(5, 30, n)
        V, R = VT + VF, RT + RF
        f = VF.sum() / V.sum(); yT, yF = RT.sum() / VT.sum(), RF.sum() / VF.sum()
        fi = VF / V
        comp = (fi - f) * (yF - yT)
        within = (1 - fi) * (RT / VT - yT) + fi * (RF / VF - yF)
        assert np.allclose(R / V - R.sum() / V.sum(), comp + within, atol=1e-9)


def test_p3_p4_comparative_statics_random():
    rng = np.random.default_rng(3)
    for _ in range(500):
        n = rng.integers(5, 60)
        ps, r = rng.uniform(10, 500, n), rng.uniform(0, 1, n)
        front = set(D.pareto_front(ps, r))
        lams = np.sort(rng.uniform(0, 5, 8))
        lead = [int(np.argmax(D.adjusted_score(ps, r, l))) for l in lams]
        assert all(i in front for i in lead)                                  # P3: maximisers are Pareto-efficient
        assert all(r[a] >= r[b] - 1e-12 for a, b in zip(lead[:-1], lead[1:]))  # P4: risk of the maximiser never rises with lambda


def test_crossing_formula():
    rng = np.random.default_rng(4)
    for _ in range(500):
        ps_i, ps_j = rng.uniform(50, 500, 2); r_i, r_j = rng.uniform(0, 1, 2)
        lam = D.crossing(ps_i, r_i, ps_j, r_j)
        if lam is not None:
            assert abs(D.adjusted_score(ps_i, r_i, lam) - D.adjusted_score(ps_j, r_j, lam)) < 1e-8


def test_real_data_results():
    r = json.load(open("results_dss/results_decision.json"))
    assert r["aggregation"]["max_abs_region_gap"] < 1e-9 and abs(r["aggregation"]["national_weighted_mean"] - 100) < 1e-9
    assert r["lever_identity_max_abs_error_thb"] < 1e-6
    assert r["leaders_on_frontier"] and r["leader_risk_nonincreasing"] and r["crossings_verified"]
    assert sum(v["n"] for v in r["typology"].values()) == 77


def test_deterministic():
    a = open("results_dss/results_decision.json").read()
    subprocess.run([sys.executable, "te_decision.py", "provinces_2024.csv", "panel.csv", "--outdir", "/tmp/dss_rerun"], check=True, capture_output=True)
    assert a == open("/tmp/dss_rerun/results_decision.json").read()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except Exception as ex:  # noqa
                fails += 1; print("FAIL", name, repr(ex))
    sys.exit(1 if fails else 0)
