"""
How much of a monthly payroll print is signal, and how does it compare with the
pace needed to keep unemployment stable (the breakeven)?

1. Sampling error: BLS says the monthly payroll change has a 90% confidence
   interval of about +/- config.NFP_CI_90 thousand. A print inside that band
   around breakeven is statistically indistinguishable from breakeven.
2. Breakeven: (a) published estimates you enter in config.py, and
   (b) our own simple calculation:
       breakeven = [pop16 x LFPR x g/12 + pop16 x dLFPR/12] x (1 - u)
   where g = annual population growth, dLFPR = yearly change in participation,
   u = unemployment rate. Both inputs come from config.py.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from common import (config, rnd, load_series, load_vintages, Vintages, style, save_chart,
                    log, NAVY, ORANGE, GREY, LIGHT)


def own_breakeven():
    """Our transparent breakeven estimate in thousands per month, or None if inputs are blank."""
    g, drift = config.POP_GROWTH_ANNUAL_PCT, config.LFPR_DRIFT_PP_PER_YEAR
    if g is None or drift is None:
        return None, "Own breakeven: not calculated (POP_GROWTH_ANNUAL_PCT and LFPR_DRIFT_PP_PER_YEAR are set to None in config.py)"
    pop = load_series("CNP16OV").iloc[-1]
    lfpr = load_series("CIVPART").iloc[-1] / 100
    u = load_series("UNRATE").iloc[-1] / 100
    from_pop = pop * lfpr * (g / 100) / 12
    from_lfpr = pop * (drift / 100) / 12
    be = (from_pop + from_lfpr) * (1 - u)
    text = (f"Own breakeven = ({pop:,.0f}k x {lfpr:.3f} x {g}%/12 + {pop:,.0f}k x {drift}pp/12) "
            f"x (1 - {u:.3f}) = {be:,.0f}k per month")
    return be, text


def main():
    style()
    vint = Vintages(load_vintages())
    latest = load_series("PAYEMS").diff()

    months = latest.dropna().index[-36:]
    df = pd.DataFrame({
        "latest": latest.reindex(months),
        "first": [vint.change(m, vint.nth_release(m, 1)) if vint.nth_release(m, 1) is not None else np.nan
                  for m in months],
    }, index=months)
    df["avg3_latest"] = df["latest"].rolling(3).mean()
    rnd(df, 0).to_csv(config.TABLES / "noise_last36m.csv")

    be_own, be_text = own_breakeven()
    lo, hi = config.BREAKEVEN_LOW, config.BREAKEVEN_HIGH
    have_band = lo is not None and hi is not None
    be_mid = (lo + hi) / 2 if have_band else be_own
    ci = config.NFP_CI_90

    fig, ax = plt.subplots(figsize=(9, 4.4))
    if have_band:
        ax.axhspan(lo, hi, color=ORANGE, alpha=0.18, lw=0, label=f"Breakeven range ({lo} to {hi}k)")
    elif be_own is not None:
        ax.axhline(be_own, color=ORANGE, lw=1.4, ls="--", label=f"Breakeven (own estimate, {be_own:.0f}k)")
    ax.bar(df.index, df["latest"], width=20, color=LIGHT, edgecolor=NAVY, lw=0.6,
           yerr=ci, ecolor=GREY, capsize=0, error_kw={"lw": 0.8},
           label=f"Monthly change today, with 90% sampling band (±{ci}k)")
    ax.scatter(df.index, df["first"], color=NAVY, s=12, zorder=3, label="First print")
    ax.plot(df.index, df["avg3_latest"], color=NAVY, lw=1.8, label="3-month average")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Monthly payroll changes: signal vs sampling noise")
    ax.set_ylabel("Thousands of jobs")
    lo_y, hi_y = ax.get_ylim()
    ax.set_ylim(lo_y, hi_y + (hi_y - lo_y) * 0.25)
    ax.legend(fontsize=7.5, loc="upper left", ncol=2)
    save_chart(fig, "chart3_noise_breakeven", "BLS via FRED/ALFRED, BLS Technical Note. Breakeven: see note.")

    last24 = df.tail(24)
    lines = [be_text,
             f"Published breakeven range in config: {lo} to {hi}k" if have_band
             else "Published breakeven range: not entered yet in config.py",
             f"90% CI on one monthly print: ±{ci}k. "
             f"Rough CI on a 3-month average if errors were independent: ±{ci / np.sqrt(3):.0f}k",
             f"Latest month {df.index[-1]:%b %Y}: first print {df['first'].iloc[-1]:,.0f}k, today {df['latest'].iloc[-1]:,.0f}k",
             f"3-month average (today's data): {df['avg3_latest'].iloc[-1]:,.0f}k",
             f"Months in last 24 inside ±CI of zero (not statistically different from no growth): "
             f"{(last24['latest'].abs() <= ci).sum()} of 24"]
    if be_mid is not None:
        inside = ((last24["latest"] - be_mid).abs() <= ci).sum()
        lines.append(f"Months in last 24 inside ±CI of breakeven midpoint ({be_mid:.0f}k): {inside} of 24")
        lines.append(f"Months in last 24 where the FIRST print was above breakeven midpoint but today's value is below: "
                     f"{((last24['first'] > be_mid) & (last24['latest'] < be_mid)).sum()}")
    log("Noise and breakeven (04)", lines)


if __name__ == "__main__":
    main()
