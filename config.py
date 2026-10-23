"""
Central settings. Every script imports this file, so settings live in one place.

FRED API key
  Saved in fred_key.txt in this folder (one line). The file is in .gitignore.

Sample
  START            first date downloaded
  REVISION_START   first reference month in the revision analysis
  COVID_EXCLUDE    months left out of statistics (the COVID swing dominates every average)

Series
  FRED_SERIES      latest values downloaded from FRED
  BLS_HH_ADJUSTED  household employment adjusted to the payroll concept (BLS research
                   series, not on FRED), downloaded from the BLS API
  VINTAGE_SERIES   series whose every historical release is downloaded from ALFRED

Sampling error
  NFP_CI_90        90% confidence interval on the monthly payroll change, in thousands.
                   BLS Employment Situation Technical Note: "on the order of plus or minus 122,000".

Wage growth consistent with 2% inflation
  WAGE_NEUTRAL_LOW / WAGE_NEUTRAL_HIGH   2% inflation plus 1% to 1.5% trend productivity growth (% a year)

Breakeven payroll growth (thousands of jobs a month)
  BREAKEVEN_LOW / BREAKEVEN_HIGH   published range, with sources in BREAKEVEN_SOURCES.
                                   Leave as None to skip the band.
  POP_GROWTH_ANNUAL_PCT            annual growth of the 16+ population (%), for the own estimate
  LFPR_DRIFT_PP_PER_YEAR           yearly change in participation (pp), for the own estimate
  Own estimate = [pop16 x LFPR x g/12 + pop16 x dLFPR/12] x (1 - u). Skipped if either input is None.
"""

from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"
DATA_MANUAL = ROOT / "data" / "manual"
CHARTS = ROOT / "outputs" / "charts"
TABLES = ROOT / "outputs" / "tables"
KEY_NUMBERS = ROOT / "outputs" / "key_numbers.txt"

for folder in [DATA_RAW, DATA_MANUAL, CHARTS, TABLES]:
    folder.mkdir(parents=True, exist_ok=True)


def get_fred_key():
    """Read the FRED key from fred_key.txt, or from an environment variable."""
    key_file = ROOT / "fred_key.txt"
    if key_file.exists():
        return key_file.read_text().strip()
    if os.environ.get("FRED_API_KEY"):
        return os.environ["FRED_API_KEY"]
    raise SystemExit(
        "No FRED API key found. Create fred_key.txt in the project folder "
        "and paste your key into it."
    )


START = "1990-01-01"
REVISION_START = "2000-01-01"
COVID_EXCLUDE = ("2020-03-01", "2021-12-01")


FRED_SERIES = {
    "PAYEMS": "Total nonfarm payrolls, establishment survey (thousands)",
    "USPRIV": "Total private payrolls, establishment survey (thousands)",
    "CE16OV": "Civilian employment, household survey (thousands)",
    "UNRATE": "Unemployment rate (%)",
    "CLF16OV": "Civilian labour force (thousands)",
    "CIVPART": "Labour force participation rate (%)",
    "CNP16OV": "Civilian non-institutional population 16+ (thousands)",
    "ICSA": "Initial jobless claims, weekly",
    "CCSA": "Continuing jobless claims, weekly",
    "JTSJOL": "JOLTS job openings (thousands)",
    "ADPMNUSNERSA": "ADP total private employment (persons)",
    "DGS2": "2-year Treasury yield, daily (%)",
    "USREC": "NBER recession indicator (1 = recession)",
    "DEXCHUS": "Yuan per US dollar, daily noon NY (H.10)",
    "DEXKOUS": "Won per US dollar, daily noon NY (H.10)",
    "CES0500000003": "Average hourly earnings, total private ($)",
    "ECIWAG": "Employment Cost Index, wages and salaries, private industry (index)",
    "PCEPILFE": "Core PCE price index",
    "CPILFESL": "Core CPI index",
}

BLS_HH_ADJUSTED = "LNS16000000"

VINTAGE_SERIES = "PAYEMS"


NFP_CI_90 = 122

WAGE_NEUTRAL_LOW = 3.0
WAGE_NEUTRAL_HIGH = 3.5


BREAKEVEN_LOW = 15
BREAKEVEN_HIGH = 87
BREAKEVEN_SOURCES = [
    "Bick (St. Louis Fed), Breakeven Employment Growth: Estimate Range Widens in 2026, 24 Mar 2026, "
    "https://www.stlouisfed.org/on-the-economy/2026/mar/breakeven-employment-growth-estimate-range-widens-2026",
]

POP_GROWTH_ANNUAL_PCT = None
LFPR_DRIFT_PP_PER_YEAR = None
