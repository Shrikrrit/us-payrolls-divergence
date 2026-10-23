This folder holds series that do not come from FRED. Each file is a CSV with two columns: date,value
(date as YYYY-MM-DD, value as a number).

household_payroll_concept.csv  BLS household employment adjusted to the payroll concept (series LNS16000000, thousands).
                               Written by src/01_data_pull.py from the BLS public API. If the API is unavailable,
                               download LNS16000000 from https://data.bls.gov/timeseries/LNS16000000 and save it here
                               in the same format.
