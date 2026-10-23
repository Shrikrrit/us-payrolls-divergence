"""
How far apart are the payroll (establishment) survey and the household survey?

The two surveys measure different things:
  payrolls  = number of JOBS on employer payrolls (a person with 2 jobs counts twice)
  household = number of PEOPLE employed (includes self-employed, farm, unpaid family workers)

For a like-for-like comparison we use BLS household employment "adjusted to the payroll
concept" (series LNS16000000, downloaded by 01_data_pull.py into data/manual/).
If that file is missing the script falls back to the raw household series (CE16OV).

Two data problems handled here:
  1. Population-control breaks. Each January BLS updates household survey population
     estimates and does NOT revise earlier months, so the household LEVEL jumps in January.
     Cumulative level gaps therefore mix real differences with these breaks. The clean
     comparison is monthly CHANGES excluding Januaries, which is what the right panel shows.
  2. October 2025 has no household data (government shutdown). It is filled by
     straight-line interpolation and flagged.
"""

import pandas as pd
import matplotlib.pyplot as plt

from common import (config, rnd, load_series, load_manual, to_month_start, style, save_chart,
                    log, NAVY, ORANGE, GREY)


def main():
    style()
    pay = to_month_start(load_series("PAYEMS"))

    hh = load_manual("household_payroll_concept.csv")
    if hh is not None:
        hh, hh_label = to_month_start(hh), "Household survey, adjusted to payroll concept"
    else:
        hh, hh_label = to_month_start(load_series("CE16OV")), "Household survey (raw CE16OV, NOT adjusted)"

    df = pd.concat({"payrolls": pay, "household": hh}, axis=1).dropna(subset=["payrolls"])
    gaps = df.index[df["household"].isna() & (df.index > df["household"].first_valid_index())]
    df["household"] = df["household"].interpolate(limit_area="inside")
    df = df.dropna()

    base = pd.Timestamp("2019-12-01")
    cum = (df - df.loc[base]) / 1000
    cum["gap"] = cum["payrolls"] - cum["household"]

    ch = df.diff()
    ch_exjan = ch.copy()
    ch_exjan.loc[ch_exjan.index.month == 1] = float("nan")
    avg6 = ch_exjan.rolling(6, min_periods=5).mean()

    out = pd.concat({"level": df, "cum_change_since_dec19_m": cum,
                     "monthly_change_exjan_k": ch_exjan, "avg6_change_exjan_k": avg6}, axis=1)
    rnd(out, 2).to_csv(config.TABLES / "divergence_monthly.csv")

    jan = ch[(ch.index.month == 1) & (ch.index >= "2019-01-01")]

    plot_start = pd.Timestamp("2021-01-01")
    c = cum[cum.index >= plot_start]
    a = avg6[avg6.index >= plot_start]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

    ax1.plot(c.index, c["payrolls"], color=NAVY, lw=1.8, label="Payrolls")
    ax1.plot(c.index, c["household"], color=ORANGE, lw=1.8, label="Household (payroll concept)")
    for d in c.index[c.index.month == 1]:
        ax1.axvline(d, color=GREY, lw=0.6, ls=":")
    ax1.axhline(0, color="black", lw=0.8)
    ax1.set_title("Level since Dec 2019 (dotted: January breaks)")
    ax1.set_ylabel("Millions")
    ax1.legend(loc="lower right", fontsize=8)

    ax2.plot(a.index, a["payrolls"], color=NAVY, lw=1.8, label="Payrolls")
    ax2.plot(a.index, a["household"], color=ORANGE, lw=1.8, label="Household (payroll concept)")
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_title("Monthly change, 6-month avg, excl. Januaries")
    ax2.set_ylabel("Thousands")
    ax2.legend(loc="upper right", fontsize=8)
    note = "" if "adjusted" in hh_label else " Household series NOT adjusted to payroll concept."
    save_chart(fig, "chart1_divergence",
               f"BLS (CES; CPS research series LNS16000000). Oct 2025 household value interpolated.{note}")

    last = df.index[-1]
    last12 = ch_exjan.loc[ch_exjan.index > last - pd.DateOffset(months=12)]
    lines = [
        f"Household series used: {hh_label}",
        f"Latest month: {last:%b %Y}",
        "Household months with no data, filled by interpolation: "
        + (", ".join(f"{d:%b %Y}" for d in gaps) if len(gaps) else "none"),
        f"Level change since Dec 2019 (includes January breaks): payrolls {cum.loc[last, 'payrolls']:.2f}m, "
        f"household {cum.loc[last, 'household']:.2f}m, gap {cum.loc[last, 'gap']:.2f}m",
        f"Last 12 months EXCLUDING January ({last12['payrolls'].notna().sum()} months): "
        f"payrolls {last12['payrolls'].sum():,.0f}k, household {last12['household'].sum():,.0f}k",
        f"6-month average monthly change excl. January: payrolls {avg6['payrolls'].iloc[-1]:,.0f}k, "
        f"household {avg6['household'].iloc[-1]:,.0f}k",
        "January changes, payrolls vs household (k), difference is a rough break indicator: "
        + ", ".join(f"{d:%Y}: {p:,.0f} vs {h:,.0f}" for d, p, h in zip(jan.index, jan["payrolls"], jan["household"])),
        "Check the official population adjustment in each January Employment Situation release before quoting break sizes.",
    ]
    log("Divergence (03)", lines)


if __name__ == "__main__":
    main()
