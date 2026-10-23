"""
08_realtime_test.py
Can the revision bias be used in real time, and does the rates market over-react to the headline?

02_revisions.py defines regimes with today's data, which a trader would not have had.
Here every input is taken from the vintage published on the release day itself.

Real-time regime, for each reference month m, using the first release r1 of m:
  avg6_now   = average monthly change over m-5 to m, as published on r1
  avg6_prior = average monthly change over m-11 to m-6, as published on r1
  Slowing (real time) if avg6_now < avg6_prior, otherwise Accelerating (real time)

Tests (releases since 2002, COVID months March 2020 to December 2021 excluded):
  A. Revision bias by real-time regime
       rev_total = latest value minus first print, mean with Newey-West (HAC) errors
  B. Does a strong headline in a slowing regime get revised down more?
       strong = first print above the prior 3-month average known that day
  C. Does the 2-year yield move on release day reverse afterwards?
       d2y_day   = release-day close minus previous close (bp)
       d2y_after = close 10 trading days after release minus release-day close (bp)
       Regression d2y_after = a + b * d2y_day, by real-time regime. b < 0 means partial reversal.
       Fade test: average d2y_after after releases where the headline beat trend, by regime,
       compared with the average d2y_after across all releases (yields drift after releases too).

10 trading days ends before the next payroll release, so the window does not overlap it.

Outputs:
  outputs/tables/realtime_releases.csv
  outputs/tables/realtime_tests.csv

Run:  python src/08_realtime_test.py
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import config, rnd, load_series, load_vintages, Vintages, log

HOLD_DAYS = 10


def hac_mean(x):
    x = pd.Series(x).dropna()
    if len(x) < 8:
        return x.mean(), np.nan, np.nan, len(x)
    m = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return m.params[0], m.bse[0], m.tvalues[0], len(x)


def main():
    vint = Vintages(load_vintages())
    latest = load_series("PAYEMS").diff()
    dgs2 = load_series("DGS2")
    days = dgs2.index

    rows = []
    for m in vint.first_release.index:
        if m < pd.Timestamp("2002-01-01"):
            continue
        r1 = vint.nth_release(m, 1)
        if r1 is None:
            continue
        ch = [vint.change(m - pd.DateOffset(months=k), r1) for k in range(12)]
        first = ch[0]
        row = {"ref_month": m, "release_date": r1, "first": first,
               "avg6_now": np.nanmean(ch[:6]), "avg6_prior": np.nanmean(ch[6:]),
               "headline_vs_trend": first - np.nanmean(ch[1:4]),
               "rev_total": latest.get(m, np.nan) - first}
        pos = days.searchsorted(r1)
        if pos < len(days) and days[pos] == r1 and pos >= 1 and pos + HOLD_DAYS < len(days):
            row["d2y_day"] = (dgs2.iloc[pos] - dgs2.iloc[pos - 1]) * 100
            row["d2y_after"] = (dgs2.iloc[pos + HOLD_DAYS] - dgs2.iloc[pos]) * 100
        rows.append(row)

    df = pd.DataFrame(rows).set_index("ref_month")
    df["regime_rt"] = np.where(df["avg6_now"] < df["avg6_prior"], "Slowing (real time)", "Accelerating (real time)")
    df["strong"] = df["headline_vs_trend"] > 0
    c0, c1 = (pd.Timestamp(d) for d in config.COVID_EXCLUDE)
    df["covid"] = (df.index >= c0) & (df.index <= c1)
    rnd(df, 2).to_csv(config.TABLES / "realtime_releases.csv")
    clean = df[~df["covid"]]

    tests, lines = [], []
    regimes = ["Accelerating (real time)", "Slowing (real time)"]

    for rg in regimes:
        mean, se, t, n = hac_mean(clean.loc[clean.regime_rt == rg, "rev_total"])
        tests.append({"test": "A revision bias", "group": rg, "n": n, "mean": mean, "se": se, "t": t})
        lines.append(f"A  {rg:<25} revision latest minus first: n={n:<4} mean={mean:6.1f}k  t={t:5.2f}")

    for rg in regimes:
        for strong in [True, False]:
            sub = clean[(clean.regime_rt == rg) & (clean.strong == strong)]
            mean, se, t, n = hac_mean(sub["rev_total"])
            label = f"{rg}, headline {'above' if strong else 'below'} trend"
            tests.append({"test": "B revision by headline", "group": label, "n": n, "mean": mean, "se": se, "t": t})
            lines.append(f"B  {label:<52} revision: n={n:<4} mean={mean:6.1f}k  t={t:5.2f}")

    mk = clean.dropna(subset=["d2y_day", "d2y_after"])
    for rg in regimes:
        sub = mk[mk.regime_rt == rg]
        model = sm.OLS(sub["d2y_after"], sm.add_constant(sub["d2y_day"])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        b, t = model.params["d2y_day"], model.tvalues["d2y_day"]
        tests.append({"test": "C reversal slope", "group": rg, "n": int(model.nobs), "mean": b, "se": model.bse["d2y_day"], "t": t})
        lines.append(f"C  {rg:<25} 10-day move on release-day move: n={int(model.nobs):<4} slope={b:5.2f}  t={t:5.2f}")
        for strong in [True, False]:
            s2 = sub[sub.strong == strong]
            mean, se, t2, n = hac_mean(s2["d2y_after"])
            day = s2["d2y_day"].mean()
            label = f"{rg}, headline {'above' if strong else 'below'} trend"
            tests.append({"test": "C fade", "group": label, "n": n, "mean": mean, "se": se, "t": t2, "day_move": day})
            lines.append(f"C  {label:<52} release day {day:5.1f}bp, next 10 days {mean:5.1f}bp (t={t2:5.2f}), n={n}")

    mean, se, t, n = hac_mean(mk["d2y_after"])
    tests.append({"test": "C baseline", "group": "All releases", "n": n, "mean": mean, "se": se, "t": t})
    lines.append(f"C  Baseline, all releases: next 10 days {mean:5.1f}bp (t={t:5.2f}), n={n}. Compare each group with this, not with zero.")
    rnd(pd.DataFrame(tests), 3).to_csv(config.TABLES / "realtime_tests.csv", index=False)

    last = df.dropna(subset=["first"]).iloc[-1]
    lines += ["",
              f"Latest release ({last.release_date:%d %b %Y}, {last.name:%b %Y}): real-time regime = {last.regime_rt}, "
              f"6-month average {last.avg6_now:.0f}k vs {last.avg6_prior:.0f}k in the prior 6 months",
              f"Real-time regime agrees with the hindsight regime of 02_revisions.py in "
              f"{agreement(clean):.0%} of months (recession months counted as slowing)"]
    log("Real-time regime and market follow-through (08)", lines)


def agreement(clean):
    path = config.TABLES / "revisions_by_month.csv"
    if not path.exists():
        return np.nan
    hind = pd.read_csv(path, parse_dates=["month"]).set_index("month")["regime"]
    hind = hind.replace("Recession", "Slowing")
    rt = clean["regime_rt"].str.replace(" (real time)", "", regex=False)
    both = pd.concat([rt, hind], axis=1, join="inner").dropna()
    return (both.iloc[:, 0] == both.iloc[:, 1]).mean()


if __name__ == "__main__":
    main()
