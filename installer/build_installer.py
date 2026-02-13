"""
build_installer.py — Automated build script for Beta1 Portfolio Tracker installer
Downloads embedded Python, installs dependencies, and builds the Inno Setup installer.

Usage: python installer/build_installer.py
"""
import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
import tempfile

# =============================================================================
# CONFIGURATION
# =============================================================================
PYTHON_VERSION = "3.12.8"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
PIP_BOOTSTRAP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Paths (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER_DIR = os.path.join(PROJECT_ROOT, "installer")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build", "app")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
PYTHON_DIR = os.path.join(BUILD_DIR, "python")

# Files to include in the installer
APP_FILES = [
    "app.py",
    "firebase_config.py",
    "ticker_db.py",
    "translations.py",
    "statistics.py",
    "xtb_mapping.py",
    "logo_fetcher.py",
    "ocr_reader.py",
    "requirements.txt",
    "streamlit_secrets.toml",
    "firebase_service_account.json",
    "firebase_web_config.json",
    "secret.key",
]

APP_DIRS = [
    ".streamlit",
    "assets",
]

# Inno Setup paths to search
ISCC_PATHS = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
]


def log(msg):
    print(f"  [BUILD] {msg}")


def download_file(url, dest):
    """Download a file with progress dots."""
    log(f"Downloading {os.path.basename(dest)}...")
    urllib.request.urlretrieve(url, dest)
    log(f"  -> {os.path.getsize(dest) / 1024 / 1024:.1f} MB")


def step_clean():
    """Clean previous build artifacts."""
    log("Cleaning previous build...")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)


def step_download_python():
    """Download and extract Python embeddable."""
    log(f"=== Step 1: Download Python {PYTHON_VERSION} embedded ===")
    zip_path = os.path.join(INSTALLER_DIR, f"python-{PYTHON_VERSION}-embed.zip")

    if not os.path.exists(zip_path):
        download_file(PYTHON_EMBED_URL, zip_path)
    else:
        log(f"Using cached {os.path.basename(zip_path)}")

    log("Extracting Python...")
    os.makedirs(PYTHON_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(PYTHON_DIR)

    # Enable pip in embedded Python by uncommenting import site in ._pth file
    pth_files = [f for f in os.listdir(PYTHON_DIR) if f.endswith("._pth")]
    for pth in pth_files:
        pth_path = os.path.join(PYTHON_DIR, pth)
        with open(pth_path, "r") as f:
            content = f.read()
        content = content.replace("#import site", "import site")
        with open(pth_path, "w") as f:
            f.write(content)

    log(f"Python extracted to {PYTHON_DIR}")


def step_install_pip():
    """Install pip into embedded Python."""
    log("=== Step 2: Install pip ===")
    get_pip = os.path.join(INSTALLER_DIR, "get-pip.py")

    if not os.path.exists(get_pip):
        download_file(PIP_BOOTSTRAP_URL, get_pip)

    python_exe = os.path.join(PYTHON_DIR, "python.exe")
    subprocess.run(
        [python_exe, get_pip, "--no-warn-script-location"],
        check=True,
        capture_output=True,
    )

    # Also install setuptools and wheel (needed for building some packages)
    subprocess.run(
        [python_exe, "-m", "pip", "install", "setuptools", "wheel",
         "--no-warn-script-location", "--disable-pip-version-check"],
        check=True,
        capture_output=True,
    )
    log("pip + setuptools + wheel installed successfully")


def step_install_requirements():
    """Install all app requirements into embedded Python."""
    log("=== Step 3: Install requirements ===")
    python_exe = os.path.join(PYTHON_DIR, "python.exe")
    req_file = os.path.join(PROJECT_ROOT, "requirements.txt")

    result = subprocess.run(
        [python_exe, "-m", "pip", "install",
         "-r", req_file,
         "--no-warn-script-location",
         "--disable-pip-version-check"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log(f"ERROR installing requirements:\n{result.stderr}")
        sys.exit(1)

    # Print installed packages
    result2 = subprocess.run(
        [python_exe, "-m", "pip", "list", "--format=columns"],
        capture_output=True, text=True,
    )
    pkg_count = len(result2.stdout.strip().split("\n")) - 2  # minus header
    log(f"Installed {pkg_count} packages")


def step_copy_app_files():
    """Copy application files to build directory."""
    log("=== Step 4: Copy app files ===")

    for fname in APP_FILES:
        src = os.path.join(PROJECT_ROOT, fname)
        dst = os.path.join(BUILD_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            log(f"  + {fname}")
        else:
            log(f"  ! MISSING: {fname}")

    for dname in APP_DIRS:
        src = os.path.join(PROJECT_ROOT, dname)
        dst = os.path.join(BUILD_DIR, dname)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            log(f"  + {dname}/")

    # Copy launcher
    launcher_src = os.path.join(INSTALLER_DIR, "launch.pyw")
    launcher_dst = os.path.join(BUILD_DIR, "launch.pyw")
    shutil.copy2(launcher_src, launcher_dst)
    log("  + launch.pyw")

    # Setup .streamlit/secrets.toml from streamlit_secrets.toml
    secrets_src = os.path.join(BUILD_DIR, "streamlit_secrets.toml")
    streamlit_dir = os.path.join(BUILD_DIR, ".streamlit")
    secrets_dst = os.path.join(streamlit_dir, "secrets.toml")
    if os.path.exists(secrets_src):
        os.makedirs(streamlit_dir, exist_ok=True)
        shutil.copy2(secrets_src, secrets_dst)
        log("  + .streamlit/secrets.toml (from streamlit_secrets.toml)")


def step_create_icon():
    """Create a simple icon if one doesn't exist."""
    assets_dir = os.path.join(BUILD_DIR, "assets")
    icon_path = os.path.join(assets_dir, "icon.ico")
    if not os.path.exists(icon_path):
        os.makedirs(assets_dir, exist_ok=True)
        # Create a minimal valid .ico file (16x16 blue square)
        # Using raw bytes for a tiny valid ICO
        log("Creating default icon...")
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (0, 119, 182, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 15), "B1", fill="white")
            img.save(icon_path, format="ICO", sizes=[(64, 64)])
            log("  + assets/icon.ico (generated)")
        except ImportError:
            # Fallback: create a minimal .ico from raw bytes
            _create_minimal_ico(icon_path)
            log("  + assets/icon.ico (minimal fallback)")


def _create_minimal_ico(path):
    """Create a minimal 16x16 .ico file."""
    import struct
    width, height = 16, 16
    # ICONDIR header
    header = struct.pack("<HHH", 0, 1, 1)
    # ICONDIRENTRY
    bmp_size = 40 + (width * height * 4) + (width * height // 8)
    entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, bmp_size, 22)
    # BITMAPINFOHEADER
    bih = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    # Pixel data (blue square BGRA)
    pixels = b"\xB6\x77\x00\xFF" * (width * height)
    # AND mask
    and_mask = b"\x00" * (width * height // 8)

    with open(path, "wb") as f:
        f.write(header + entry + bih + pixels + and_mask)


def step_build_installer():
    """Run Inno Setup compiler."""
    log("=== Step 5: Build installer ===")

    iscc = None
    for path in ISCC_PATHS:
        if os.path.exists(path):
            iscc = path
            break

    if not iscc:
        log("=" * 60)
        log("Inno Setup NOT FOUND!")
        log("")
        log("Please install Inno Setup 6 from:")
        log("  https://jrsoftware.org/isdl.php")
        log("")
        log("After installing, re-run this script.")
        log("=" * 60)
        log("")
        log("BUILD DIRECTORY READY at:")
        log(f"  {BUILD_DIR}")
        log("")
        log("You can manually compile the installer using:")
        log(f'  "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" "{INSTALLER_DIR}\\beta1_setup.iss"')
        return False

    iss_file = os.path.join(INSTALLER_DIR, "beta1_setup.iss")
    log(f"Compiling with: {iscc}")

    result = subprocess.run(
        [iscc, iss_file],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log(f"Inno Setup error:\n{result.stdout}\n{result.stderr}")
        return False

    installer = os.path.join(DIST_DIR, "Beta1_Portfolio_Setup.exe")
    if os.path.exists(installer):
        size_mb = os.path.getsize(installer) / 1024 / 1024
        log(f"INSTALLER READY: {installer}")
        log(f"Size: {size_mb:.1f} MB")
    return True


def main():
    print("=" * 60)
    print("  Beta1 Portfolio Tracker — Installer Builder")
    print("=" * 60)
    print()

    step_clean()
    step_download_python()
    step_install_pip()
    step_install_requirements()
    step_copy_app_files()
    step_create_icon()
    success = step_build_installer()

    print()
    if success:
        print("=" * 60)
        print("  BUILD SUCCESSFUL!")
        print(f"  Installer: dist/Beta1_Portfolio_Setup.exe")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  BUILD PARTIALLY COMPLETE")
        print(f"  App files ready in: build/app/")
        print("  Install Inno Setup and re-run to create installer")
        print("=" * 60)


if __name__ == "__main__":
    main()
