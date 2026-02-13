"""
launch.pyw — Silent launcher for Beta1 Portfolio Tracker
Starts Streamlit server and opens the app in the default browser.
No console window shown (.pyw extension).
"""
import subprocess
import sys
import os
import time
import webbrowser
import shutil
import threading

# App configuration
APP_PORT = 8501
APP_URL = f"http://localhost:{APP_PORT}"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(APP_DIR, "app.py")
PYTHON_DIR = os.path.join(APP_DIR, "python")
PYTHON_EXE = os.path.join(PYTHON_DIR, "python.exe")


def setup_secrets():
    """Copy streamlit_secrets.toml to .streamlit/secrets.toml if needed."""
    secrets_src = os.path.join(APP_DIR, "streamlit_secrets.toml")
    streamlit_dir = os.path.join(APP_DIR, ".streamlit")
    secrets_dst = os.path.join(streamlit_dir, "secrets.toml")

    if os.path.exists(secrets_src) and not os.path.exists(secrets_dst):
        os.makedirs(streamlit_dir, exist_ok=True)
        shutil.copy2(secrets_src, secrets_dst)


def wait_and_open_browser():
    """Wait for Streamlit to start, then open browser."""
    for _ in range(30):  # Wait up to 30 seconds
        time.sleep(1)
        try:
            import urllib.request
            urllib.request.urlopen(APP_URL, timeout=2)
            webbrowser.open(APP_URL)
            return
        except Exception:
            continue
    # Fallback: open anyway after 30s
    webbrowser.open(APP_URL)


def main():
    # Ensure secrets are set up
    setup_secrets()

    # Determine Python executable
    python_exe = PYTHON_EXE if os.path.exists(PYTHON_EXE) else sys.executable

    # Start Streamlit in background
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_SERVER_PORT"] = str(APP_PORT)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    cmd = [
        python_exe, "-m", "streamlit", "run", APP_FILE,
        "--server.headless", "true",
        "--server.port", str(APP_PORT),
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]

    # Start Streamlit process (hidden console on Windows)
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    process = subprocess.Popen(
        cmd,
        cwd=APP_DIR,
        env=env,
        startupinfo=startupinfo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Open browser in a separate thread
    browser_thread = threading.Thread(target=wait_and_open_browser, daemon=True)
    browser_thread.start()

    # Wait for Streamlit to exit
    process.wait()


if __name__ == "__main__":
    main()
