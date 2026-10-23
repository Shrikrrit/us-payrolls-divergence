import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def load_series(series_id):
    path = config.DATA_RAW / f"{series_id}.csv"
    if not path.exists():
        print(f"  [warning] {series_id}.csv not found, skipping it")
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    s = df.set_index("date")["value"].astype(float).dropna()
    s.name = series_id
    return s


def load_vintages():
    path = config.DATA_RAW / f"{config.VINTAGE_SERIES}_vintages.csv"
    if not path.exists():
        raise SystemExit("PAYEMS_vintages.csv missing. Run 01_data_pull.py first.")
    df = pd.read_csv(path)
    df["realtime_end"] = df["realtime_end"].replace("9999-12-31", "2200-01-01")
    for col in ["date", "realtime_start", "realtime_end"]:
        df[col] = pd.to_datetime(df[col])
    return df.dropna(subset=["value"])


class Vintages:
    
    def __init__(self, vint):
        self.lookup = {}
        for d, g in vint.groupby("date"):
            self.lookup[d] = (
                g["realtime_start"].values.astype("datetime64[ns]").astype("int64"),
                g["realtime_end"].values.astype("datetime64[ns]").astype("int64"),
                g["value"].values,
            )
        first = vint.groupby("date")["realtime_start"].min()
        self.first_release = first
        self.release_dates = sorted(pd.to_datetime(first.unique()))

    def level(self, month, asof):
        """Payroll level (thousands) for `month` as published on date `asof`."""
        entry = self.lookup.get(month)
        if entry is None:
            return float("nan")
        start, end, val = entry
        v = pd.Timestamp(asof).value
        hit = (start <= v) & (end >= v)
        return float(val[hit][0]) if hit.any() else float("nan")

    def change(self, month, asof):
        """Monthly change in payrolls for `month` as published on date `asof`."""
        prev = month - pd.DateOffset(months=1)
        return self.level(month, asof) - self.level(prev, asof)

    def nth_release(self, month, n):
        """Date of the n-th release that included `month` (n=1 first print, 2 second, 3 third)."""
        r1 = self.first_release.get(month)
        if r1 is None or pd.isna(r1):
            return None
        i = self.release_dates.index(r1) + (n - 1)
        return self.release_dates[i] if i < len(self.release_dates) else None


def load_manual(filename):
    path = config.DATA_MANUAL / filename
    if not path.exists():
        print(f"  [info] {filename} not in data/manual, using the fallback")
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    return df.set_index("date")["value"].astype(float).dropna()


def rnd(df, n):
    df = df.copy()
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(n)
    return df


def to_month_start(s):
    s = s.copy()
    s.index = s.index.to_period("M").to_timestamp()
    return s


NAVY = "#1f3b63"
ORANGE = "#d9822b"
GREY = "#8a8f98"
LIGHT = "#d6dbe3"
RED = "#b23a3a"


def style():
    plt.rcParams.update({
        "figure.figsize": (8, 4.2),
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e6e6e6",
        "grid.linewidth": 0.6,
        "axes.titleweight": "bold",
        "axes.titlesize": 11,
        "legend.frameon": False,
    })


def save_chart(fig, name, source):
    fig.text(0.01, 0.005, f"Source: {source}", fontsize=7.5, color=GREY, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = config.CHARTS / f"{name}.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  saved chart: outputs/charts/{name}.png")


def shade_recessions(ax, start=None):
    rec = load_series("USREC")
    if rec is None:
        return
    if start is not None:
        rec = rec[rec.index >= start]
    in_rec = False
    for date, flag in rec.items():
        if flag == 1 and not in_rec:
            begin, in_rec = date, True
        elif flag == 0 and in_rec:
            ax.axvspan(begin, date, color=LIGHT, alpha=0.6, lw=0)
            in_rec = False
    if in_rec:
        ax.axvspan(begin, rec.index[-1], color=LIGHT, alpha=0.6, lw=0)


def log(section, lines):
    text = f"\n=== {section} ===\n" + "\n".join(lines) + "\n"
    print(text)
    with open(config.KEY_NUMBERS, "a") as f:
        f.write(text)
