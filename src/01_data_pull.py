"""
Downloads every dataset the analysis needs from the FRED / ALFRED API and saves
them as CSV files in data/raw/.

Two kinds of download:
  1. Latest values of each series in config.FRED_SERIES  -> data/raw/<ID>.csv
  2. Every historical vintage of PAYEMS (what payrolls looked like on each
     release date)                                         -> data/raw/PAYEMS_vintages.csv
     plus the list of release (vintage) dates              -> data/raw/PAYEMS_vintagedates.csv
  3. BLS household employment adjusted to the payroll concept (LNS16000000) from the
     keyless BLS API, in 10-year chunks (the API limit)    -> data/manual/household_payroll_concept.csv
     BLS writes "-" for months with no data (October 2025, when the shutdown stopped the
     household survey). Those months are dropped and listed in key_numbers.txt.

Run with --only ID1,ID2 to download just those FRED series without touching anything else,
for example: python src/01_data_pull.py --only CES0500000003,ECIWAG

Vintages are downloaded with output_type=1 (one row per value and the period it was valid),
paged 100,000 rows at a time.
"""

import sys
import time
import requests
import pandas as pd

from common import config, log

BASE = "https://api.stlouisfed.org/fred"
KEY = config.get_fred_key()


def fred_request(endpoint, params):
    params = {**params, "api_key": KEY, "file_type": "json"}
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    raise SystemExit(f"FRED request failed: {endpoint} {params.get('series_id')}")


def get_observations(series_id, realtime=False):
    params = {"series_id": series_id, "observation_start": config.START}
    if realtime:
        params.update({
            "realtime_start": config.START,
            "realtime_end": "9999-12-31",
            "output_type": 1,
        })
    rows, offset = [], 0
    while True:
        params.update({"limit": 100000, "offset": offset})
        js = fred_request("series/observations", params)
        batch = js["observations"]
        rows.extend(batch)
        offset += len(batch)
        if offset >= int(js["count"]) or not batch:
            break
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def bls_series(series_id, first_year=1994):
    import datetime
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    headers = {"Content-type": "application/json", "User-Agent": "research-script"}
    rows, year = [], first_year
    this_year = datetime.date.today().year
    while year <= this_year:
        body = {"seriesid": [series_id], "startyear": str(year), "endyear": str(min(year + 9, this_year))}
        r = requests.post(url, json=body, headers=headers, timeout=60)
        js = r.json()
        if js.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(js.get("message"))
        for obs in js["Results"]["series"][0]["data"]:
            if obs["period"].startswith("M") and obs["period"] != "M13":
                value = pd.to_numeric(obs["value"], errors="coerce")
                rows.append({"date": f"{obs['year']}-{obs['period'][1:]}-01", "value": value})
        year += 10
    return pd.DataFrame(rows).sort_values("date")


def main():
    if "--only" in sys.argv:
        ids = sys.argv[sys.argv.index("--only") + 1].split(",")
        for sid in ids:
            print(f"Downloading {sid}")
            df = get_observations(sid)
            df[["date", "value"]].to_csv(config.DATA_RAW / f"{sid}.csv", index=False)
            print(f"  {sid}: {df['date'].iloc[0]} to {df['date'].iloc[-1]} ({len(df)} obs)")
        return

    config.KEY_NUMBERS.write_text("KEY NUMBERS FOR THE NOTE (auto-generated)\n")

    done, failed = [], []
    for sid, label in config.FRED_SERIES.items():
        print(f"Downloading {sid}: {label}")
        try:
            df = get_observations(sid)
            df[["date", "value"]].to_csv(config.DATA_RAW / f"{sid}.csv", index=False)
            done.append(f"{sid}: {df['date'].iloc[0]} to {df['date'].iloc[-1]} ({len(df)} obs)")
        except SystemExit as e:
            failed.append(f"{sid}: {e}")

    sid = config.VINTAGE_SERIES
    print(f"Downloading all vintages of {sid} (can take a minute)")
    vint = get_observations(sid, realtime=True)
    vint = vint[["date", "realtime_start", "realtime_end", "value"]]
    vint.to_csv(config.DATA_RAW / f"{sid}_vintages.csv", index=False)

    js = fred_request("series/vintagedates", {"series_id": sid, "realtime_start": config.START, "limit": 10000})
    vd = pd.DataFrame({"vintage_date": js["vintage_dates"]})
    vd.to_csv(config.DATA_RAW / f"{sid}_vintagedates.csv", index=False)

    try:
        print(f"Downloading {config.BLS_HH_ADJUSTED} from the BLS API")
        hh = bls_series(config.BLS_HH_ADJUSTED)
        missing = hh.loc[hh["value"].isna(), "date"].tolist()
        hh = hh.dropna()
        hh.to_csv(config.DATA_MANUAL / "household_payroll_concept.csv", index=False)
        done.append(f"{config.BLS_HH_ADJUSTED} (BLS): {hh['date'].iloc[0]} to {hh['date'].iloc[-1]} ({len(hh)} obs)"
                    + (f", no data for: {', '.join(missing)}" if missing else ""))
    except Exception as e:
        failed.append(f"{config.BLS_HH_ADJUSTED} (BLS API): {e}. Download it by hand, see data/manual/README.md.")

    log("Data pull", done + [
        f"PAYEMS vintages: {len(vint):,} rows, {len(vd)} vintage dates "
        f"({vd['vintage_date'].iloc[0]} to {vd['vintage_date'].iloc[-1]})",
    ] + ([f"FAILED: {x}" for x in failed] or ["All series downloaded"]))


if __name__ == "__main__":
    main()
