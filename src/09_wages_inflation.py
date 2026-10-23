"""
09_wages_inflation.py
Is the labour market adding to inflation? Wage growth and core inflation.

The link from jobs to inflation runs through wages. Wage growth is consistent with 2%
inflation when it equals 2% plus trend productivity growth, taken here as 1% to 1.5%,
so 3.0% to 3.5% a year (config.WAGE_NEUTRAL_LOW / HIGH).

Measures
  Average hourly earnings, total private (CES0500000003), monthly
    year on year, 3-month and 6-month annualised
  Employment Cost Index, wages and salaries, private industry (ECIWAG), quarterly
    year on year and quarter on quarter annualised. The ECI fixes the mix of jobs, so it is
    not distorted by shifts between high- and low-paid work, unlike average hourly earnings.
  Core PCE (PCEPILFE) and core CPI (CPILFESL), monthly
    year on year and 3-month annualised
Each is compared with its 2018-19 average, when inflation was close to 2%.

  annualised n-month rate = ((x_t / x_(t-n)) ^ (12 / n) - 1) x 100

Outputs:
  outputs/tables/wages_inflation.csv

Run:  python src/09_wages_inflation.py
      (download the series first: python src/01_data_pull.py --only CES0500000003,ECIWAG,PCEPILFE,CPILFESL)
"""

import pandas as pd

from common import config, load_series, log


def annualised(s, n, periods_per_year):
    return ((s / s.shift(n)) ** (periods_per_year / n) - 1) * 100


def summary(sid, name, freq):
    s = load_series(sid)
    if s is None:
        return None, f"{name}: {sid}.csv missing, run 01_data_pull.py --only {sid}"
    ppy = 12 if freq == "M" else 4
    yoy = s.pct_change(ppy) * 100
    short = annualised(s, 3 if freq == "M" else 1, ppy)
    six = annualised(s, 6, ppy) if freq == "M" else pd.Series(dtype=float)
    base = yoy.loc["2018":"2019"].mean()
    last = s.index[-1]
    row = {"series": name, "id": sid, "latest": last.strftime("%Y-%m"),
           "yoy": yoy.iloc[-1], "short_annualised": short.iloc[-1],
           "six_month_annualised": six.iloc[-1] if len(six) else float("nan"),
           "yoy_12m_ago": yoy.iloc[-1 - ppy], "avg_2018_19": base}
    label = "3m ann." if freq == "M" else "q/q ann."
    text = (f"{name:<38} latest {last:%b %Y}: y/y {row['yoy']:.1f}%, {label} {row['short_annualised']:.1f}%"
            + (f", 6m ann. {row['six_month_annualised']:.1f}%" if freq == "M" else "")
            + f" | y/y a year ago {row['yoy_12m_ago']:.1f}% | 2018-19 avg {base:.1f}%")
    return row, text


def main():
    rows, lines = [], []
    for sid, name, freq in [("CES0500000003", "Average hourly earnings, private", "M"),
                            ("ECIWAG", "ECI wages and salaries, private", "Q"),
                            ("PCEPILFE", "Core PCE prices", "M"),
                            ("CPILFESL", "Core CPI", "M")]:
        row, text = summary(sid, name, freq)
        lines.append(text)
        if row:
            rows.append(row)
    if rows:
        pd.DataFrame(rows).round(2).to_csv(config.TABLES / "wages_inflation.csv", index=False)
    lines.append(f"Wage growth consistent with 2% inflation (2% plus 1% to 1.5% productivity): "
                 f"{config.WAGE_NEUTRAL_LOW:.1f}% to {config.WAGE_NEUTRAL_HIGH:.1f}%")
    log("Wages and core inflation (09)", lines)


if __name__ == "__main__":
    main()
