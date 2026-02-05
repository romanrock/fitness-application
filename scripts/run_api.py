import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.config import API_PORT, RUN_MODE


def venv_python():
    venv = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / (
        "python.exe" if sys.platform.startswith("win") else "python"
    )
    return venv if venv.exists() else None


def main():
    py = venv_python() or sys.executable
    reload_flag = ["--reload"] if RUN_MODE != "prod" else []
    subprocess.run(
        [str(py), "-m", "uvicorn", "apps.api.main:app", *reload_flag, "--host", "0.0.0.0", "--port", str(API_PORT)],
        check=True,
        cwd=str(ROOT),
    )


if __name__ == "__main__":
    main()
