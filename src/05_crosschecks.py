"""
Do other labour market indicators agree with payrolls?

Four panels since 2022:
  (a) Jobless claims: initial (4-week average) and continuing
  (b) JOLTS job openings
  (c) ADP private employment vs BLS private payrolls (3-month average monthly change)
  (d) Unemployment rate

Also a table comparing each indicator today, 12 months ago and its 2018-2019 average
(a 'normal' tight labour market before COVID).
"""

import pandas as pd
import matplotlib.pyplot as plt

from common import config, load_series, to_month_start, style, save_chart, log, NAVY, ORANGE, GREY


def summary_row(name, s, unit):
    """Latest value, value 12 months earlier and 2018-2019 average for one indicator."""
    s = s.dropna()
    last_date = s.index[-1]
    yr_ago = s[s.index <= last_date - pd.DateOffset(years=1)]
    pre = s[(s.index >= "2018-01-01") & (s.index <= "2019-12-31")]
    return {"indicator": name, "unit": unit, "latest_date": last_date.date(),
            "latest": s.iloc[-1], "12m_ago": yr_ago.iloc[-1] if len(yr_ago) else None,
            "avg_2018_19": pre.mean() if len(pre) else None}


def main():
    style()
    start = pd.Timestamp("2022-01-01")
    icsa, ccsa = load_series("ICSA"), load_series("CCSA")
    jolts, unrate = load_series("JTSJOL"), load_series("UNRATE")
    adp, priv = load_series("ADPMNUSNERSA"), load_series("USPRIV")

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.4))
    rows = []

    ax = axes[0, 0]
    if icsa is not None:
        ic4 = icsa.rolling(4).mean() / 1000
        ax.plot(ic4[ic4.index >= start], color=NAVY, lw=1.6, label="Initial, 4-wk avg (lhs)")
        rows.append(summary_row("Initial claims, 4-wk avg", icsa.rolling(4).mean() / 1000, "thousands"))
    if ccsa is not None:
        ax_r = ax.twinx()
        ax_r.plot(ccsa[ccsa.index >= start] / 1e6, color=ORANGE, lw=1.6, label="Continuing (rhs)")
        ax_r.set_ylabel("Millions", color=ORANGE)
        ax_r.grid(False)
        rows.append(summary_row("Continuing claims", ccsa / 1e6, "millions"))
        ax.plot([], [], color=ORANGE, lw=1.6, label="Continuing (rhs)")
    ax.set_title("(a) Jobless claims")
    ax.set_ylabel("Thousands")
    ax.legend(fontsize=7.5, loc="upper left")

    ax = axes[0, 1]
    if jolts is not None:
        j = jolts / 1000
        ax.plot(j[j.index >= start], color=NAVY, lw=1.6)
        rows.append(summary_row("JOLTS job openings", j, "millions"))
    ax.set_title("(b) JOLTS job openings")
    ax.set_ylabel("Millions")

    ax = axes[1, 0]
    if priv is not None:
        p3 = to_month_start(priv).diff().rolling(3).mean()
        ax.plot(p3[p3.index >= start], color=NAVY, lw=1.6, label="BLS private payrolls")
        rows.append(summary_row("BLS private payrolls, 3m avg change", p3, "thousands"))
    if adp is not None:
        a3 = (to_month_start(adp) / 1000).diff().rolling(3).mean()
        ax.plot(a3[a3.index >= start], color=ORANGE, lw=1.6, label="ADP private employment")
        rows.append(summary_row("ADP private, 3m avg change", a3, "thousands"))
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("(c) Private job gains, 3-month average")
    ax.set_ylabel("Thousands per month")
    ax.legend(fontsize=7.5)

    ax = axes[1, 1]
    if unrate is not None:
        ax.plot(unrate[unrate.index >= start], color=NAVY, lw=1.6)
        rows.append(summary_row("Unemployment rate", unrate, "%"))
    ax.set_title("(d) Unemployment rate")
    ax.set_ylabel("%")

    save_chart(fig, "chart4_crosschecks", "BLS, US Department of Labor, ADP Research via FRED.")

    tbl = pd.DataFrame(rows)
    tbl.round(2).to_csv(config.TABLES / "crosschecks_summary.csv", index=False)
    lines = [f"{r['indicator']:<38} latest ({r['latest_date']}) {r['latest']:,.2f} | 12m ago "
             f"{r['12m_ago'] if r['12m_ago'] is None else round(r['12m_ago'], 2)} | 2018-19 avg "
             f"{r['avg_2018_19'] if r['avg_2018_19'] is None else round(r['avg_2018_19'], 2)} {r['unit']}"
             for r in rows]
    log("Cross-checks (05)", lines)


if __name__ == "__main__":
    main()
