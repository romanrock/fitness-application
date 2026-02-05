import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    venv = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / (
        "python.exe" if sys.platform.startswith("win") else "python"
    )
    py = str(venv) if venv.exists() else sys.executable
    cmd = [py, "-m", "pytest", "-q"]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


if __name__ == "__main__":
    main()
