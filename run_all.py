import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["01_data_pull.py", "02_revisions.py", "03_divergence.py",
         "04_noise_breakeven.py", "05_crosschecks.py", "06_market_reaction.py", "07_asian_fx.py",
         "08_realtime_test.py", "09_wages_inflation.py"]

if "--skip-download" in sys.argv:
    STEPS = STEPS[1:]
    key = ROOT / "outputs" / "key_numbers.txt"
    if key.exists():
        text = key.read_text().split("\n=== Revisions (02) ===")[0]
        key.write_text(text)

for step in STEPS:
    print(f"\n>>> Running {step}")
    result = subprocess.run([sys.executable, str(ROOT / "src" / step)], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"Stopped: {step} failed. Read the error above, or see the Troubleshooting section.")

print("\nDone. Results in outputs/key_numbers.txt, charts in outputs/charts/")
