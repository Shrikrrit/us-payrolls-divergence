"""
Example of transmission: how far do US payroll releases travel into Asian FX?
The managed yuan is compared with a freely floating Asian currency (the Korean won).

Idea: on payroll release days, US news moves the 2-year Treasury yield. If the
yuan were free floating, USD/CNY would move with that yield change roughly as
much as USD/KRW does. The PBoC sets a daily fixing and limits how far the onshore
rate can move from it, so we expect a smaller response. The gap between the two
is a measure of how much the managed regime dampens US data shocks.

Data (FRED, H.10 noon buying rates in New York, so they capture the 8:30am payroll
release on the same day):
  DEXCHUS  yuan per US dollar
  DEXKOUS  won per US dollar
Downloaded automatically by this script if they are not already in data/raw/.

Timing problem and fix:
  FRED's noon New York won rate largely reflects the Seoul session, which closes
  before the 8:30am US release, so the won only reacts the NEXT trading day.
  The onshore yuan market only extended trading into New York hours in 2016.
  To capture the reaction whichever session prices it, we measure each currency over
  a two-day window: from the close before the release to the close on the next
  trading day.

Method:
  For each payroll release since 2005 (from 06_market_reaction.py):
    fx_pct = % change in USD/CNY (or USD/KRW) from the day before the release
             to the trading day after it
    d2y_bp = change in the US 2-year yield on release day (basis points)
  Regress fx_pct on d2y_bp with Newey-West standard errors. The slope is the % move
  in the currency per 10bp move in the 2-year yield. Run separately for:
    2005 to Jul 2015  (before the August 2015 fixing reform)
    Aug 2015 onwards  (after the reform)
  Also: average absolute move on release days vs all other days ("release-day premium").
"""

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
import matplotlib.pyplot as plt

from common import config, rnd, load_series, style, save_chart, log, NAVY, ORANGE, GREY

FX = {"DEXCHUS": "Yuan (USD/CNY)", "DEXKOUS": "Won (USD/KRW)"}
REFORM = pd.Timestamp("2015-08-11")


def download_if_missing(series_id):
    path = config.DATA_RAW / f"{series_id}.csv"
    if path.exists():
        return
    print(f"Downloading {series_id} from FRED")
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": series_id, "api_key": config.get_fred_key(),
                             "file_type": "json", "observation_start": config.START},
                     timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["observations"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df[["date", "value"]].to_csv(path, index=False)


def daily_pct_change(s):
    """% change from the previous available day (skips holidays)."""
    s = s.dropna()
    return (s / s.shift(1) - 1) * 100


def fit(df, ycol):
    """Slope of fx % move on 2y yield move, rescaled to 'per 10bp', with HAC errors."""
    d = df[[ycol, "d2y_bp"]].dropna()
    if len(d) < 20:
        return None
    m = sm.OLS(d[ycol], sm.add_constant(d["d2y_bp"] / 10)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return {"n": int(m.nobs), "beta_pct_per_10bp": m.params["d2y_bp"], "se": m.bse["d2y_bp"],
            "t": m.tvalues["d2y_bp"], "r2": m.rsquared}


def main():
    style()
    for sid in FX:
        download_if_missing(sid)

    rel_path = config.TABLES / "market_reaction_releases.csv"
    if not rel_path.exists():
        raise SystemExit("Run 06_market_reaction.py first.")
    rel = pd.read_csv(rel_path, parse_dates=["release_date", "ref_month"]).set_index("release_date")
    rel = rel[~rel["covid"]]

    chg, two_day = {}, {}
    for sid in FX:
        fx = load_series(sid).dropna()
        chg[sid] = daily_pct_change(fx)
        two_day[sid] = (fx.shift(-1) / fx.shift(1) - 1) * 100
        vals = []
        for d in rel.index:
            i = fx.index.searchsorted(d)
            if i == 0 or i + 1 >= len(fx):
                vals.append(np.nan)
                continue
            after = i + 1 if fx.index[i] == d else i
            vals.append((fx.iloc[after] / fx.iloc[i - 1] - 1) * 100 if after < len(fx) else np.nan)
        rel[sid] = vals

    periods = {"2005 to Jul 2015": rel[rel.index < REFORM], "Aug 2015 onwards": rel[rel.index >= REFORM]}
    rows = []
    for sid, name in FX.items():
        for pname, sub in periods.items():
            res = fit(sub, sid)
            if res:
                rows.append({"currency": name, "period": pname, **res})
    betas = pd.DataFrame(rows)
    rnd(betas, 3).to_csv(config.TABLES / "asian_fx_betas.csv", index=False)

    premium = {}
    for sid in FX:
        w = two_day[sid][two_day[sid].index >= REFORM].dropna()
        on = rel.loc[rel.index >= REFORM, sid].abs().mean()
        off = w[~w.index.isin(rel.index)].abs().mean()
        premium[sid] = (on, off, on / off if off else np.nan)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [1.4, 1]})
    post = rel[rel.index >= REFORM]
    colors = {"DEXCHUS": NAVY, "DEXKOUS": ORANGE}
    for sid, name in FX.items():
        d = post[[sid, "d2y_bp"]].dropna()
        ax1.scatter(d["d2y_bp"], d[sid], s=12, alpha=0.55, color=colors[sid], label=name)
        b = betas[(betas.currency == name) & (betas.period == "Aug 2015 onwards")]
        if not b.empty:
            xs = np.linspace(d["d2y_bp"].quantile(0.02), d["d2y_bp"].quantile(0.98), 20)
            ax1.plot(xs, b["beta_pct_per_10bp"].iloc[0] * xs / 10, color=colors[sid], lw=1.8)
    ax1.axhline(0, color="black", lw=0.6)
    ax1.axvline(0, color="black", lw=0.6)
    ax1.set_xlabel("US 2-year yield change on payroll day (bp)")
    ax1.set_ylabel("Two-day change in USD per currency (%)")
    ax1.set_title("Payroll days since Aug 2015")
    ax1.legend(fontsize=8, loc="upper left")

    labels, vals, errs, cols = [], [], [], []
    for _, r in betas.iterrows():
        labels.append(f"{r.currency.split()[0]}\n{r.period.replace(' onwards', '+').replace('2005 to ', 'to ')}")
        vals.append(r.beta_pct_per_10bp)
        errs.append(1.96 * r.se)
        cols.append(NAVY if r.currency.startswith("Yuan") else ORANGE)
    ax2.bar(range(len(vals)), vals, yerr=errs, color=cols, capsize=4, ecolor=GREY)
    ax2.set_xticks(range(len(vals)))
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.axhline(0, color="black", lw=0.6)
    ax2.set_title("FX move per 10bp in US 2y (95% band)")
    ax2.set_ylabel("% per 10bp")
    save_chart(fig, "chart6_asian_fx", "Federal Reserve H.10 and H.15 via FRED, BLS via ALFRED. FX over two days around release. Excl. COVID.")

    lines = []
    for _, r in betas.iterrows():
        lines.append(f"{r.currency:<15} {r.period:<17} n={r.n:<4} beta={r.beta_pct_per_10bp:.3f}% per 10bp "
                     f"(t={r.t:.2f}), R2={r.r2:.2f}")
    post_b = betas[betas.period == "Aug 2015 onwards"].set_index("currency")["beta_pct_per_10bp"]
    post_t = betas[betas.period == "Aug 2015 onwards"].set_index("currency")["t"]
    if len(post_b) == 2 and post_b.iloc[1] != 0:
        lines.append(f"Post-2015 yuan sensitivity as share of won sensitivity: "
                     f"{post_b['Yuan (USD/CNY)'] / post_b['Won (USD/KRW)']:.0%}"
                     + (f" (won estimate not significant, t={post_t['Won (USD/KRW)']:.2f}: read as comparable, not as a precise ratio)"
                        if abs(post_t['Won (USD/KRW)']) < 1.96 else ""))
    for sid, (on, off, ratio) in premium.items():
        lines.append(f"{FX[sid]:<15} post-2015 average absolute two-day move: around payrolls {on:.3f}%, other windows {off:.3f}%, "
                     f"ratio {ratio:.2f}x")
    lines.append("Note: FX measured over two days (close before release to next trading day) because the noon NY "
                 "won rate mostly reflects the Seoul session. DEXCHUS is the onshore rate, managed via the daily fixing.")
    log("Asian FX example (07)", lines)


if __name__ == "__main__":
    main()
