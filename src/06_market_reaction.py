"""
Does the rates market react to the headline print, to revisions of earlier months, or both?

For every Employment Situation release since 2005:
  headline_vs_trend = first print minus the 3-month average known on that day
                      (a PROXY for the surprise, since consensus forecasts need Bloomberg)
  revision_prior2   = how much the two previous months were revised in that release
  d2y_bp            = change in the 2-year Treasury yield on release day, in basis points

Regression (Newey-West standard errors, COVID months excluded):
  d2y_bp = a + b1 * headline_vs_trend/100 + b2 * revision_prior2/100
b1 and b2 are basis points per 100k jobs.
A second regression adds the change in the unemployment rate in the same report
(unemp_change, per 0.1pp). Unemployment is barely revised, so today's series is close
to what was published on the day. The yield change is the release-day close minus
the previous available close. The regression is repeated on the last 5 years, and with
the 1% most extreme values of each driver removed (e.g. the January 2022 release, which
revised the two prior months up by about 700k).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

from common import (config, rnd, load_series, load_vintages, Vintages, style, save_chart,
                    log, NAVY, ORANGE)


def main():
    style()
    vint = Vintages(load_vintages())
    dgs2 = load_series("DGS2")
    unrate = load_series("UNRATE")
    if dgs2 is None:
        log("Market reaction (06)", ["DGS2 missing, skipped"])
        return

    rows = []
    months = [m for m in vint.first_release.index if m >= pd.Timestamp("2005-01-01")]
    for m in months:
        r1 = vint.nth_release(m, 1)
        prev_m = m - pd.DateOffset(months=1)
        r_prev = vint.first_release.get(prev_m)
        if r1 is None or r_prev is None or pd.isna(r_prev):
            continue
        first = vint.change(m, r1)
        prior3 = np.nanmean([vint.change(m - pd.DateOffset(months=k), r1) for k in (1, 2, 3)])
        rev = sum(vint.change(m - pd.DateOffset(months=k), r1) - vint.change(m - pd.DateOffset(months=k), r_prev)
                  for k in (1, 2))
        on_day = dgs2[dgs2.index == r1]
        before = dgs2[dgs2.index < r1]
        if on_day.empty or before.empty:
            continue
        rows.append({"release_date": r1, "ref_month": m, "first_print": first,
                     "headline_vs_trend": first - prior3, "revision_prior2": rev,
                     "unemp_change": unrate.get(m, np.nan) - unrate.get(prev_m, np.nan) if unrate is not None else np.nan,
                     "d2y_bp": (on_day.iloc[0] - before.iloc[-1]) * 100})

    df = pd.DataFrame(rows).set_index("release_date")
    c0, c1 = (pd.Timestamp(d) for d in config.COVID_EXCLUDE)
    df["covid"] = (df["ref_month"] >= c0) & (df["ref_month"] <= c1)
    rnd(df, 2).to_csv(config.TABLES / "market_reaction_releases.csv")
    clean = df[~df["covid"]].dropna(subset=["headline_vs_trend", "revision_prior2", "d2y_bp"])

    X = sm.add_constant(clean[["headline_vs_trend", "revision_prior2"]] / 100)
    model = sm.OLS(clean["d2y_bp"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    (config.TABLES / "market_reaction_regression.txt").write_text(model.summary().as_text())

    recent = clean[clean.index >= clean.index.max() - pd.DateOffset(years=5)]
    Xr = sm.add_constant(recent[["headline_vs_trend", "revision_prior2"]] / 100)
    model_r = sm.OLS(recent["d2y_bp"], Xr).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    lo_h, hi_h = clean["headline_vs_trend"].quantile([0.01, 0.99])
    lo_r, hi_r = clean["revision_prior2"].quantile([0.01, 0.99])
    trim = clean[clean["headline_vs_trend"].between(lo_h, hi_h) & clean["revision_prior2"].between(lo_r, hi_r)]
    Xt = sm.add_constant(trim[["headline_vs_trend", "revision_prior2"]] / 100)
    model_t = sm.OLS(trim["d2y_bp"], Xt).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    cu = clean.dropna(subset=["unemp_change"])
    Xu = sm.add_constant(pd.concat([cu[["headline_vs_trend", "revision_prior2"]] / 100, cu["unemp_change"] * 10], axis=1))
    model_u = sm.OLS(cu["d2y_bp"], Xu).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, col, label, b in [(ax1, "headline_vs_trend", "Headline minus prior 3-month average (k)", model.params["headline_vs_trend"]),
                              (ax2, "revision_prior2", "Revision to prior 2 months (k)", model.params["revision_prior2"])]:
        ax.scatter(clean[col], clean["d2y_bp"], s=10, color=NAVY, alpha=0.5)
        xs = np.linspace(clean[col].quantile(0.01), clean[col].quantile(0.99), 50)
        ax.plot(xs, model.params["const"] + b * xs / 100, color=ORANGE, lw=1.8)
        ax.axhline(0, color="black", lw=0.6)
        ax.axvline(0, color="black", lw=0.6)
        ax.set_xlabel(label)
        ax.set_title(f"{b:.1f} bp per 100k")
    ax1.set_ylabel("2-year yield change on release day (bp)")
    save_chart(fig, "chart5_market_reaction", "BLS via ALFRED, Federal Reserve H.15 via FRED. Releases since 2005 excl. COVID.")

    def fmt(mdl, name):
        p = mdl.params, mdl.tvalues
        return (f"{name}: n={int(mdl.nobs)}, headline {p[0]['headline_vs_trend']:.2f}bp/100k (t={p[1]['headline_vs_trend']:.2f}), "
                f"revisions {p[0]['revision_prior2']:.2f}bp/100k (t={p[1]['revision_prior2']:.2f}), R2={mdl.rsquared:.2f}")

    log("Market reaction (06)", [
        fmt(model, "Since 2005"),
        fmt(model_r, "Last 5 years"),
        fmt(model_t, "Excl. 1% tails"),
        fmt(model_u, "With unemployment") + f", unemployment {model_u.params['unemp_change']:.2f}bp per +0.1pp (t={model_u.tvalues['unemp_change']:.2f})",
        "Note: headline_vs_trend is a proxy for the surprise. With Bloomberg consensus the fit would be tighter.",
    ])


if __name__ == "__main__":
    main()
