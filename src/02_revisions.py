"""
How much do payroll prints get revised, and are revisions biased at turning points?

For every month since 2000 we record the monthly job gain as it was published:
  first   = first print (released the month after)
  second  = as published one month later
  third   = as published two months later (last sample-based revision)
  latest  = today's value (after annual benchmark and seasonal revisions)

Revisions:
  rev_sample    = third - first   (new survey responses arriving)
  rev_benchmark = latest - third  (annual benchmark to tax records + seasonal factors)
  rev_total     = latest - first

We then compare revisions across three regimes, using today's data:
  Recession     NBER recession month
  Slowing       6-month average job gain below its level 6 months earlier
  Accelerating  all other months
Means are tested with Newey-West (HAC) standard errors, because revisions in nearby months
are correlated. March 2020 to December 2021 is excluded from the statistics.

Benchmark by year: the annual benchmark released each February revises payrolls up to March
of the previous year. A calendar year Y is therefore fully benchmarked only once the February
release of year Y+2 is out, so the by-year table stops two years before the latest data month.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

from common import (config, rnd, load_series, load_vintages, Vintages, style, save_chart,
                    shade_recessions, log, NAVY, ORANGE, GREY, RED)


def hac_mean(x):
    """Mean of x with a Newey-West (HAC) standard error.
    HAC corrects for revisions in nearby months being correlated."""
    x = pd.Series(x).dropna()
    if len(x) < 8:
        return x.mean(), np.nan, np.nan
    model = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return model.params[0], model.bse[0], model.tvalues[0]


def main():
    style()
    vint = Vintages(load_vintages())

    months = [m for m in vint.first_release.index if m >= pd.Timestamp(config.REVISION_START)]
    latest = load_series("PAYEMS").diff()
    rows = []
    for m in months:
        r1, r2, r3 = (vint.nth_release(m, n) for n in (1, 2, 3))
        rows.append({
            "month": m,
            "first_release_date": r1,
            "first": vint.change(m, r1),
            "second": vint.change(m, r2) if r2 is not None else np.nan,
            "third": vint.change(m, r3) if r3 is not None else np.nan,
            "latest": latest.get(m, np.nan),
        })
    df = pd.DataFrame(rows).set_index("month")
    df["rev_sample"] = df["third"] - df["first"]
    df["rev_benchmark"] = df["latest"] - df["third"]
    df["rev_total"] = df["latest"] - df["first"]

    trend = latest.rolling(6).mean()
    slowing = trend < trend.shift(6)
    rec = load_series("USREC")
    df["regime"] = np.where(slowing.reindex(df.index).fillna(False), "Slowing", "Accelerating")
    if rec is not None:
        df.loc[rec.reindex(df.index).fillna(0) == 1, "regime"] = "Recession"

    c0, c1 = (pd.Timestamp(d) for d in config.COVID_EXCLUDE)
    df["covid"] = (df.index >= c0) & (df.index <= c1)
    rnd(df, 1).to_csv(config.TABLES / "revisions_by_month.csv")
    clean = df[~df["covid"]]

    stats = []
    for regime in ["All", "Accelerating", "Slowing", "Recession"]:
        sub = clean if regime == "All" else clean[clean["regime"] == regime]
        for col in ["rev_sample", "rev_benchmark", "rev_total"]:
            x = sub[col].dropna()
            mean, se, t = hac_mean(x)
            stats.append({
                "regime": regime, "revision": col, "n": len(x),
                "mean_k": mean, "hac_se_k": se, "t_stat": t,
                "median_k": x.median(), "sd_k": x.std(),
                "mean_abs_k": x.abs().mean(), "share_negative": (x < 0).mean(),
            })
    st = pd.DataFrame(stats)
    rnd(st, 2).to_csv(config.TABLES / "revisions_by_regime.csv", index=False)

    recent = df[["first_release_date", "first", "second", "third", "latest", "rev_total"]].dropna(subset=["first"]).tail(24)
    rnd(recent, 0).to_csv(config.TABLES / "revisions_recent_24m.csv")

    last_full_year = df.dropna(subset=["first"]).index.max().year - 2
    bench = clean["rev_benchmark"].groupby(clean.index.year).sum(min_count=1).dropna()
    bench = bench[bench.index <= last_full_year]
    bench.round(0).rename("sum_latest_minus_third_k").to_csv(config.TABLES / "benchmark_by_year.csv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [2.2, 1]})
    cum12 = df["rev_total"].where(~df["covid"]).rolling(12, min_periods=10).sum() / 1000
    shade_recessions(ax1, start=config.REVISION_START)
    ax1.plot(cum12.index, cum12.values, color=NAVY, lw=1.6)
    ax1.axhline(0, color="black", lw=0.8)
    ax1.set_title("First prints vs today: 12-month cumulative revision")
    ax1.set_ylabel("Millions of jobs (latest minus first print)")

    tot = st[(st["revision"] == "rev_total") & (st["regime"] != "All")].set_index("regime")
    order = [r for r in ["Accelerating", "Slowing", "Recession"] if r in tot.index and tot.loc[r, "n"] > 0]
    colors = {"Accelerating": NAVY, "Slowing": ORANGE, "Recession": RED}
    ax2.bar(order, tot.loc[order, "mean_k"], color=[colors[r] for r in order],
            yerr=1.96 * tot.loc[order, "hac_se_k"].fillna(0), capsize=4, ecolor=GREY)
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_title("Avg revision by regime")
    ax2.set_ylabel("Thousands per month (95% HAC band)")
    save_chart(fig, "chart2_revisions", "BLS via ALFRED (St. Louis Fed), NBER. Excludes Mar 2020 to Dec 2021.")

    def line(regime, col):
        r = st[(st["regime"] == regime) & (st["revision"] == col)].iloc[0]
        return (f"{regime:<12} {col:<14} n={r.n:<4} mean={r.mean_k:7.1f}k  t={r.t_stat:5.2f}  "
                f"mean|rev|={r.mean_abs_k:6.1f}k  share negative={r.share_negative:.0%}")

    lines = [line(rg, c) for rg in ["All", "Accelerating", "Slowing", "Recession"]
             for c in ["rev_total", "rev_sample"] if not st[(st.regime == rg) & (st.revision == c)].empty
             and st[(st.regime == rg) & (st.revision == c)].n.iloc[0] > 0]
    last12 = df.dropna(subset=["first"]).tail(12)
    lines += [
        "",
        f"Last 12 months: sum of first prints = {last12['first'].sum():,.0f}k, "
        f"sum as of today = {last12['latest'].sum():,.0f}k, "
        f"difference = {last12['rev_total'].sum():,.0f}k",
        f"Last 12 months: months revised down = {(last12['rev_total'] < 0).sum()} of {last12['rev_total'].notna().sum()}",
        f"Benchmark+seasonal revision by year, fully benchmarked years only (through {last_full_year}) (k): " + ", ".join(f"{y}: {v:,.0f}" for y, v in bench.tail(6).items()),
    ]
    log("Revisions (02)", lines)


if __name__ == "__main__":
    main()
