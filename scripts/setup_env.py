import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
BIN_DIR = VENV_DIR / ("Scripts" if sys.platform.startswith("win") else "bin")
PY = BIN_DIR / ("python.exe" if sys.platform.startswith("win") else "python")


def run(cmd):
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main():
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if not PY.exists():
        raise SystemExit("Virtualenv python not found. Remove .venv and re-run setup.")

    run([str(PY), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(PY), "-m", "pip", "install", "-r", "requirements.txt"])

    print("Setup complete.")
    print("Next:")
    print(f"  source {VENV_DIR}/bin/activate")
    print("  python3 scripts/run_pipeline.py")


if __name__ == "__main__":
    main()
