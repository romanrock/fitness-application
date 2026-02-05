import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    venv_py = os.path.join(root, ".venv", "bin", "python")
    py = venv_py if os.path.exists(venv_py) else sys.executable
    env = os.environ.copy()
    env.setdefault("FITNESS_AUTH_DISABLED", "1")
    env.setdefault("PORT", "8001")

    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "apps.api.main:app", "--port", env["PORT"]],
        cwd=root,
        env=env,
    )

    try:
        url = f"http://127.0.0.1:{env['PORT']}/api/health"
        deadline = time.time() + 15
        last_err = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        print("Smoke OK")
                        return
            except Exception as exc:
                last_err = exc
                time.sleep(0.5)
        raise SystemExit(f"Smoke failed: {last_err}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
