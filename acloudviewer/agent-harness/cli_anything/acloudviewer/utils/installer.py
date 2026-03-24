"""ACloudViewer auto-installation utilities.

Detects platform, queries GitHub releases, and installs the matching
Python wheel or desktop application binary.

Download page: https://asher-1.github.io/ACloudViewer/
GitHub releases: https://github.com/Asher-1/ACloudViewer/releases
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

GITHUB_REPO = "Asher-1/ACloudViewer"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
HOMEPAGE = "https://asher-1.github.io/ACloudViewer/"

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

DEFAULT_APP_DIR = Path.home() / ".local" / "share" / "ACloudViewer"


# ── Platform detection ───────────────────────────────────────────────────

@dataclass
class PlatformInfo:
    os_name: str            # linux, darwin, windows
    os_id: str              # ubuntu, centos, macos, windows
    os_version: str         # 20.04, 22.04, etc.
    arch: str               # x86_64, arm64
    python_version: tuple[int, int]
    glibc_version: str      # 2.31, 2.35, etc. (Linux only)
    has_nvidia_gpu: bool

    @property
    def python_tag(self) -> str:
        return f"cp{self.python_version[0]}{self.python_version[1]}"

    @property
    def ubuntu_tag(self) -> str:
        """e.g. 'ubuntu20.04'."""
        return f"ubuntu{self.os_version}" if self.os_id == "ubuntu" else ""

    @property
    def manylinux_tag(self) -> str:
        """e.g. 'manylinux_2_31_x86_64'."""
        if not self.glibc_version:
            return ""
        glibc = self.glibc_version.replace(".", "_")
        arch = "x86_64" if self.arch in ("x86_64", "amd64") else "aarch64"
        return f"manylinux_{glibc}_{arch}"

    @property
    def arch_tag(self) -> str:
        if self.arch in ("x86_64", "amd64"):
            return "amd64"
        if self.arch in ("arm64", "aarch64"):
            return "ARM64"
        return self.arch


def detect_platform() -> PlatformInfo:
    os_name = platform.system().lower()
    arch = platform.machine()
    py_ver = (sys.version_info.major, sys.version_info.minor)

    os_id = "unknown"
    os_version = ""
    glibc_version = ""
    has_nvidia = False

    if IS_LINUX:
        os_id, os_version = _detect_linux_distro()
        glibc_version = _detect_glibc_version()
        has_nvidia = _detect_nvidia_gpu()
    elif IS_MACOS:
        os_id = "macos"
        mac_ver = platform.mac_ver()[0]
        os_version = mac_ver if mac_ver else ""
    elif IS_WINDOWS:
        os_id = "windows"
        os_version = platform.version()

    return PlatformInfo(
        os_name=os_name,
        os_id=os_id,
        os_version=os_version,
        arch=arch,
        python_version=py_ver,
        glibc_version=glibc_version,
        has_nvidia_gpu=has_nvidia,
    )


def _detect_linux_distro() -> tuple[str, str]:
    try:
        info: dict[str, str] = {}
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    key, _, val = line.strip().partition("=")
                    info[key] = val.strip('"')
        os_id = info.get("ID", "unknown")
        os_version = info.get("VERSION_ID", "")
        return os_id, os_version
    except FileNotFoundError:
        return "unknown", ""


def _detect_glibc_version() -> str:
    try:
        out = subprocess.check_output(
            ["ldd", "--version"], text=True, stderr=subprocess.STDOUT,
        )
        m = re.search(r"(\d+\.\d+)", out.split("\n")[0])
        return m.group(1) if m else ""
    except Exception:
        return ""


def _detect_nvidia_gpu() -> bool:
    return shutil.which("nvidia-smi") is not None


# ── GitHub release discovery ─────────────────────────────────────────────

@dataclass
class ReleaseAsset:
    name: str
    download_url: str
    size: int

    @property
    def size_mb(self) -> float:
        return self.size / (1024 * 1024)


@dataclass
class ReleaseInfo:
    tag: str
    name: str
    prerelease: bool
    published_at: str
    assets: list[ReleaseAsset] = field(default_factory=list)

    @property
    def version(self) -> str:
        return self.tag.lstrip("v")

    @property
    def label(self) -> str:
        kind = "beta" if self.prerelease else "stable"
        return f"{self.tag} ({kind})"


def fetch_releases(
    include_prerelease: bool = True,
    max_releases: int = 5,
    timeout: int = 120,
) -> list[ReleaseInfo]:
    """Fetch releases from GitHub API."""
    url = f"{GITHUB_API_RELEASES}?per_page={max_releases}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise InstallError(f"Cannot reach GitHub API: {e}") from e

    releases: list[ReleaseInfo] = []
    for r in data:
        if not include_prerelease and r.get("prerelease"):
            continue
        assets = [
            ReleaseAsset(
                name=a["name"],
                download_url=a["browser_download_url"],
                size=a["size"],
            )
            for a in r.get("assets", [])
        ]
        releases.append(ReleaseInfo(
            tag=r["tag_name"],
            name=r.get("name", ""),
            prerelease=r.get("prerelease", False),
            published_at=r.get("published_at", ""),
            assets=assets,
        ))
    return releases


def get_latest_release(
    channel: Literal["stable", "beta", "any"] = "any",
) -> ReleaseInfo:
    releases = fetch_releases(include_prerelease=(channel != "stable"))
    if not releases:
        raise InstallError("No releases found on GitHub.")
    if channel == "stable":
        for r in releases:
            if not r.prerelease:
                return r
        raise InstallError("No stable release found.")
    if channel == "beta":
        for r in releases:
            if r.prerelease:
                return r
        raise InstallError("No beta release found.")
    return releases[0]


# ── Asset matching ───────────────────────────────────────────────────────

def find_matching_wheel(
    release: ReleaseInfo,
    plat: PlatformInfo,
    cpu_only: bool = False,
) -> ReleaseAsset | None:
    """Find the best matching Python wheel for this platform."""
    pytag = plat.python_tag

    if IS_LINUX:
        return _match_linux_wheel(release, pytag, plat, cpu_only)
    elif IS_MACOS:
        return _match_macos_wheel(release, pytag, plat)
    elif IS_WINDOWS:
        return _match_windows_wheel(release, pytag, cpu_only)
    return None


def _match_linux_wheel(
    release: ReleaseInfo, pytag: str, plat: PlatformInfo, cpu_only: bool,
) -> ReleaseAsset | None:
    prefix = "cloudviewer_cpu-" if cpu_only else "cloudviewer-"
    manylinux = plat.manylinux_tag

    exact = [
        a for a in release.assets
        if a.name.startswith(prefix)
        and f"-{pytag}-{pytag}-" in a.name
        and manylinux in a.name
    ]
    if exact:
        return exact[0]

    compatible = sorted(
        [
            a for a in release.assets
            if a.name.startswith(prefix)
            and f"-{pytag}-{pytag}-" in a.name
            and "manylinux" in a.name
            and "x86_64" in a.name
        ],
        key=lambda a: a.name,
    )
    if compatible:
        return compatible[0]

    return None


def _match_macos_wheel(
    release: ReleaseInfo, pytag: str, plat: PlatformInfo,
) -> ReleaseAsset | None:
    is_arm = plat.arch in ("arm64", "aarch64")
    tag_pref = "arm64" if is_arm else "x86_64"

    matches = [
        a for a in release.assets
        if a.name.startswith("cloudviewer-")
        and not a.name.startswith("cloudviewer_cpu-")
        and f"-{pytag}-{pytag}-" in a.name
        and "macosx" in a.name
        and tag_pref in a.name
    ]
    if matches:
        return matches[0]

    universal = [
        a for a in release.assets
        if a.name.startswith("cloudviewer-")
        and f"-{pytag}-{pytag}-" in a.name
        and "macosx" in a.name
    ]
    return universal[0] if universal else None


def _match_windows_wheel(
    release: ReleaseInfo, pytag: str, cpu_only: bool,
) -> ReleaseAsset | None:
    prefix = "cloudviewer_cpu-" if cpu_only else "cloudviewer-"
    matches = [
        a for a in release.assets
        if a.name.startswith(prefix)
        and f"-{pytag}-{pytag}-" in a.name
        and "win_amd64" in a.name
    ]
    return matches[0] if matches else None


def find_matching_app(
    release: ReleaseInfo,
    plat: PlatformInfo,
    cpu_only: bool = False,
) -> ReleaseAsset | None:
    """Find the desktop app installer for this platform."""
    if IS_LINUX:
        ubuntu_tag = plat.ubuntu_tag
        if not ubuntu_tag:
            ubuntu_tag = _closest_ubuntu_tag(plat.glibc_version)
        cuda_tag = "cpu" if cpu_only else "cuda"
        candidates = [
            a for a in release.assets
            if a.name.startswith("ACloudViewer-")
            and a.name.endswith(".run")
            and ubuntu_tag in a.name
            and f"-{cuda_tag}-" in a.name
        ]
        if not candidates and not cpu_only:
            candidates = [
                a for a in release.assets
                if a.name.startswith("ACloudViewer-")
                and a.name.endswith(".run")
                and ubuntu_tag in a.name
                and "-cpu-" in a.name
            ]
        return candidates[0] if candidates else None

    elif IS_MACOS:
        arch_tag = plat.arch_tag
        candidates = [
            a for a in release.assets
            if a.name.startswith("ACloudViewer-")
            and a.name.endswith(".dmg")
            and arch_tag in a.name
        ]
        return candidates[0] if candidates else None

    elif IS_WINDOWS:
        cuda_tag = "cpu" if cpu_only else "cuda"
        candidates = [
            a for a in release.assets
            if a.name.startswith("ACloudViewer-")
            and a.name.endswith(".exe")
            and f"-{cuda_tag}-" in a.name
        ]
        if not candidates and not cpu_only:
            candidates = [
                a for a in release.assets
                if a.name.startswith("ACloudViewer-")
                and a.name.endswith(".exe")
                and "-cpu-" in a.name
            ]
        return candidates[0] if candidates else None

    return None


def _closest_ubuntu_tag(glibc_version: str) -> str:
    glibc_to_ubuntu = {
        "2.27": "ubuntu18.04",
        "2.31": "ubuntu20.04",
        "2.35": "ubuntu22.04",
        "2.39": "ubuntu24.04",
    }
    if glibc_version in glibc_to_ubuntu:
        return glibc_to_ubuntu[glibc_version]
    try:
        ver = float(glibc_version)
    except (ValueError, TypeError):
        return "ubuntu20.04"
    if ver < 2.31:
        return "ubuntu18.04"
    if ver < 2.35:
        return "ubuntu20.04"
    if ver < 2.39:
        return "ubuntu22.04"
    return "ubuntu24.04"


# ── Installation ─────────────────────────────────────────────────────────

class InstallError(Exception):
    pass


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    """Render an ASCII progress bar: [████████░░░░░░] 45% 120/267 MB."""
    if total <= 0:
        done_mb = current / (1024 * 1024)
        return f"  {done_mb:.1f} MB downloaded..."
    pct = min(current * 100 // total, 100)
    filled = width * current // total
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    done_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    return f"  [{bar}] {pct}% {done_mb:.0f}/{total_mb:.0f} MB"


def _download_with_progress(
    url: str,
    dest: Path,
    label: str = "",
    timeout: int = 1800,
    max_retries: int = 3,
) -> Path:
    """Download a file with progress bar and retry.

    Prefers curl/wget for reliability; falls back to urllib with retry
    and a visual ASCII progress bar.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    display_name = label or url.split("/")[-1]

    curl = shutil.which("curl")
    wget = shutil.which("wget")

    if curl:
        print(f"  Downloading {display_name} ...")
        result = subprocess.run(
            [curl, "-L", "-o", str(dest), "--progress-bar",
             "--connect-timeout", "30", "--max-time", str(timeout),
             "--retry", str(max_retries), "--retry-delay", "5", url],
            timeout=timeout + 60,
        )
        if result.returncode != 0:
            raise InstallError(f"curl download failed (exit {result.returncode})")
        return dest

    if wget:
        print(f"  Downloading {display_name} ...")
        result = subprocess.run(
            [wget, "-O", str(dest), "--timeout=" + str(timeout),
             f"--tries={max_retries + 1}", "--show-progress", url],
            timeout=timeout + 60,
        )
        if result.returncode != 0:
            raise InstallError(f"wget download failed (exit {result.returncode})")
        return dest

    if not IS_WINDOWS:
        print("  Tip: install curl or wget for faster, more reliable downloads.")
    print(f"  Downloading {display_name} (urllib) ...")

    import http.client
    import time

    last_error: Exception | None = None
    chunk_size = 1024 * 256

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=min(timeout, 300))
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    print(f"\r{_progress_bar(downloaded, total)}", end="", flush=True)

            if total:
                print()
            if total and downloaded < total:
                raise InstallError(
                    f"Incomplete download: got {downloaded}/{total} bytes"
                )
            return dest

        except (
            urllib.error.URLError, TimeoutError, OSError,
            http.client.IncompleteRead,
        ) as e:
            last_error = e
            if attempt < max_retries:
                wait = 5 * (2 ** (attempt - 1))
                print(f"\n  Retry {attempt}/{max_retries} in {wait}s ({e}) ...")
                time.sleep(wait)
                if dest.exists():
                    dest.unlink()
            else:
                print()

    raise InstallError(
        f"Download failed after {max_retries} attempts: {last_error}"
    )


def install_wheel(
    asset: ReleaseAsset,
    pip_args: list[str] | None = None,
) -> dict:
    """Download and pip-install a cloudViewer wheel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / asset.name
        print(f"Downloading {asset.name} ({asset.size_mb:.0f} MB)...")
        _download_with_progress(asset.download_url, dest, label=asset.name)

        cmd = [sys.executable, "-m", "pip", "install", str(dest)]
        cmd += pip_args or []
        print(f"Installing with pip...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise InstallError(
                f"pip install failed (exit {result.returncode}):\n"
                f"{result.stderr[:1000]}"
            )

    version = _get_cloudviewer_version()
    return {
        "package": asset.name,
        "version": version,
        "status": "installed",
    }


def install_app(
    asset: ReleaseAsset,
    install_dir: Path | None = None,
) -> dict:
    """Download and install the ACloudViewer desktop application."""
    target = install_dir or DEFAULT_APP_DIR
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / asset.name
        print(f"Downloading {asset.name} ({asset.size_mb:.0f} MB)...")
        _download_with_progress(asset.download_url, dest, label=asset.name)

        if IS_LINUX and asset.name.endswith(".run"):
            dest.chmod(0o755)
            return _install_linux_run(dest, target)

        elif IS_MACOS and asset.name.endswith(".dmg"):
            return _install_macos_dmg(dest, target)

        elif IS_WINDOWS and asset.name.endswith(".exe"):
            return _install_windows_exe(dest, target)

    return {"status": "failed", "message": "Unsupported platform for auto-install."}


def install_app_from_file(
    file_path: Path,
    install_dir: Path | None = None,
) -> dict:
    """Install ACloudViewer from a local installer file (.run/.dmg/.exe).

    Supports both Qt Installer Framework .run files and makeself archives.
    """
    if not file_path.exists():
        raise InstallError(f"File not found: {file_path}")

    target = install_dir or DEFAULT_APP_DIR
    suffix = file_path.suffix.lower()

    if suffix == ".run" and IS_LINUX:
        file_path.chmod(0o755)
        return _install_linux_run(file_path, target)

    elif suffix == ".dmg" and IS_MACOS:
        target.mkdir(parents=True, exist_ok=True)
        return _install_macos_dmg(file_path, target)

    elif suffix == ".exe" and IS_WINDOWS:
        target.mkdir(parents=True, exist_ok=True)
        return _install_windows_exe(file_path, target)

    else:
        raise InstallError(
            f"Unsupported file type '{suffix}' for this platform. "
            f"Expected: {'.run' if IS_LINUX else '.dmg' if IS_MACOS else '.exe'}"
        )


def _install_linux_run(run_file: Path, target: Path) -> dict:
    """Install a Linux .run file — tries Qt IFW first, then makeself."""
    is_qt_ifw = _is_qt_ifw_installer(run_file)

    if is_qt_ifw:
        return _install_qt_ifw(run_file, target)

    target.mkdir(parents=True, exist_ok=True)
    bin_dir = target / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {run_file.name} to {target}...")
    result = subprocess.run(
        [str(run_file), "--noexec", "--target", str(bin_dir)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        result = subprocess.run(
            [str(run_file), "--prefix", str(target)],
            capture_output=True, text=True, timeout=120,
        )
    if result.returncode != 0:
        return {
            "status": "failed",
            "message": (
                f"Extraction failed. Run manually:\n"
                f"  chmod +x {run_file} && {run_file}"
            ),
        }

    binary = _find_binary_in_dir(target)
    if binary:
        return {
            "status": "installed",
            "binary": str(binary),
            "install_dir": str(target),
            "hint": f"export ACV_BINARY={binary}",
        }
    return {
        "status": "extracted",
        "install_dir": str(target),
        "message": f"Extracted to {target}, but binary not found. Check contents.",
    }


def _is_qt_ifw_installer(run_file: Path) -> bool:
    """Detect if a .run file is a Qt Installer Framework binary."""
    try:
        result = subprocess.run(
            [str(run_file), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        return "Qt Installer Framework" in result.stdout
    except Exception:
        return False


def _install_qt_ifw(run_file: Path, target: Path) -> dict:
    """Install using Qt Installer Framework headless mode."""
    if target.exists() and any(target.iterdir()):
        import shutil as _shutil
        _shutil.rmtree(target)

    print(f"Installing {run_file.name} to {target} (Qt IFW headless)...")
    result = subprocess.run(
        [str(run_file), "in",
         "--accept-licenses", "--confirm-command",
         "--root", str(target)],
        capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        return {
            "status": "failed",
            "message": f"Qt IFW install failed (exit {result.returncode}): {stderr[:500]}",
        }

    binary = _find_binary_in_dir(target)
    if binary:
        return {
            "status": "installed",
            "binary": str(binary),
            "install_dir": str(target),
            "hint": f"export ACV_BINARY={binary}",
        }

    return {
        "status": "extracted",
        "install_dir": str(target),
        "message": f"Installed to {target}, but binary not found. List with: ls {target}",
    }


def _install_macos_dmg(dmg_path: Path, target: Path) -> dict:
    """Mount DMG, run the Qt IFW installer silently, then unmount."""
    volume = None
    try:
        print(f"  Mounting {dmg_path.name} ...")
        mount_result = subprocess.run(
            ["hdiutil", "attach", str(dmg_path), "-nobrowse", "-noverify"],
            capture_output=True, text=True, timeout=60,
        )
        if mount_result.returncode != 0:
            return {
                "status": "downloaded", "path": str(dmg_path),
                "message": (
                    f"Could not mount DMG: {mount_result.stderr.strip()}\n"
                    f"Open {dmg_path} manually and drag ACloudViewer to /Applications."
                ),
            }

        for line in mount_result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                volume = parts[-1].strip()

        if not volume or not Path(volume).is_dir():
            return {
                "status": "downloaded", "path": str(dmg_path),
                "message": "DMG mounted but volume not found. Open manually.",
            }

        installer_apps = list(Path(volume).glob("*.app"))
        if not installer_apps:
            _detach_volume(volume)
            return {
                "status": "downloaded", "path": str(dmg_path),
                "message": "No .app found inside DMG. Open manually.",
            }

        installer_app = installer_apps[0]
        macos_dir = installer_app / "Contents" / "MacOS"
        installer_bin = None
        if macos_dir.is_dir():
            for f in macos_dir.iterdir():
                if f.is_file() and os.access(f, os.X_OK):
                    installer_bin = f
                    break

        if not installer_bin:
            _detach_volume(volume)
            return {
                "status": "downloaded", "path": str(dmg_path),
                "message": (
                    f"No executable found in {installer_app.name}. "
                    f"Open {dmg_path} manually."
                ),
            }

        print(f"  Installing to {target} ...")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "minimal"
        install_result = subprocess.run(
            [str(installer_bin), "--root", str(target),
             "--accept-licenses", "--accept-messages",
             "--confirm-command", "install"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        _detach_volume(volume)
        volume = None

        if install_result.returncode != 0:
            return {
                "status": "downloaded", "path": str(dmg_path),
                "message": (
                    f"Installer exited with code {install_result.returncode}.\n"
                    f"{install_result.stderr[:500]}\n"
                    f"Try opening {dmg_path} manually."
                ),
            }

        binary = _find_binary_in_dir(target)
        if not binary:
            app_bundle = target / "ACloudViewer.app" / "Contents" / "MacOS" / "ACloudViewer"
            if app_bundle.is_file():
                binary = app_bundle
        if binary:
            return {
                "status": "installed",
                "binary": str(binary),
                "install_dir": str(target),
                "hint": f"export ACV_BINARY={binary}",
            }
        return {
            "status": "installed",
            "install_dir": str(target),
            "message": f"Installed to {target} but binary not auto-detected. Check contents.",
        }

    except subprocess.TimeoutExpired:
        if volume:
            _detach_volume(volume)
        return {
            "status": "downloaded", "path": str(dmg_path),
            "message": "Installer timed out. Open DMG manually.",
        }
    except Exception as e:
        if volume:
            _detach_volume(volume)
        return {
            "status": "downloaded", "path": str(dmg_path),
            "message": f"Auto-install failed ({e}). Open DMG manually.",
        }


def _install_windows_exe(exe_path: Path, target: Path) -> dict:
    """Run a Qt IFW .exe installer silently on Windows."""
    keep_path = target / exe_path.name
    shutil.copy2(exe_path, keep_path)

    try:
        print(f"  Installing to {target} ...")
        install_result = subprocess.run(
            [str(keep_path), "--root", str(target),
             "--accept-licenses", "--accept-messages",
             "--confirm-command", "install"],
            capture_output=True, text=True, timeout=600,
        )
        if install_result.returncode != 0:
            return {
                "status": "downloaded",
                "path": str(keep_path),
                "message": (
                    f"Installer exited with code {install_result.returncode}.\n"
                    f"{install_result.stderr[:500]}\n"
                    f"Run {keep_path} manually to install."
                ),
            }

        binary = _find_binary_in_dir(target)
        if binary:
            return {
                "status": "installed",
                "binary": str(binary),
                "install_dir": str(target),
                "hint": f"set ACV_BINARY={binary}",
            }
        return {
            "status": "installed",
            "install_dir": str(target),
            "message": f"Installed to {target} but binary not auto-detected.",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "downloaded",
            "path": str(keep_path),
            "message": f"Installer timed out. Run {keep_path} manually.",
        }
    except Exception as e:
        return {
            "status": "downloaded",
            "path": str(keep_path),
            "message": f"Auto-install failed ({e}). Run {keep_path} manually.",
        }


def _detach_volume(volume: str) -> None:
    """Safely detach a mounted DMG volume."""
    try:
        subprocess.run(
            ["hdiutil", "detach", volume],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass


def _find_binary_in_dir(directory: Path) -> Path | None:
    """Search for ACloudViewer binary/launcher in a directory tree."""
    if IS_MACOS:
        app_binary = directory / "ACloudViewer.app" / "Contents" / "MacOS" / "ACloudViewer"
        if app_binary.is_file():
            return app_binary
        names = ["ACloudViewer"]
    elif IS_WINDOWS:
        names = ["ACloudViewer.bat", "ACloudViewer.exe"]
    else:
        names = ["ACloudViewer.sh", "ACloudViewer"]

    for root, _dirs, files in os.walk(directory):
        for name in names:
            if name in files:
                return Path(root) / name
    return None


# ── Verification ─────────────────────────────────────────────────────────

def _get_cloudviewer_version() -> str | None:
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import cloudViewer as cv3d; print(cv3d.__version__)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def check_installation() -> dict:
    """Comprehensive check of ACloudViewer installation status."""
    from .acloudviewer_backend import ACloudViewerBackend

    plat = detect_platform()
    binary = ACloudViewerBackend.find_binary()
    binary_version = ACloudViewerBackend.get_version() if binary else None
    cv_version = _get_cloudviewer_version()

    status: dict = {
        "platform": {
            "os": f"{plat.os_id} {plat.os_version}".strip(),
            "arch": plat.arch,
            "python": f"{plat.python_version[0]}.{plat.python_version[1]}",
            "glibc": plat.glibc_version or "N/A",
            "nvidia_gpu": plat.has_nvidia_gpu,
        },
        "binary": {
            "found": binary is not None,
            "path": binary,
            "version": binary_version,
        },
        "python_package": {
            "found": cv_version is not None,
            "version": cv_version,
        },
        "ready": binary is not None,
    }

    if not binary or not cv_version:
        status["install_suggestions"] = _build_suggestions(plat, binary, cv_version)

    return status


def _build_suggestions(
    plat: PlatformInfo,
    binary: str | None,
    cv_version: str | None,
) -> list[dict]:
    suggestions: list[dict] = []

    if not binary:
        suggestions.append({
            "component": "ACloudViewer binary (desktop app)",
            "priority": "required",
            "auto_install": "cli-anything-acloudviewer install app",
            "manual": f"Download from {HOMEPAGE}",
            "details": _binary_install_hint(plat),
        })

    if not cv_version:
        suggestions.append({
            "component": "cloudViewer Python package",
            "priority": "optional (for Python bindings)",
            "auto_install": "cli-anything-acloudviewer install wheel",
            "manual": f"Download .whl from {HOMEPAGE} → pip install cloudviewer-*.whl",
        })

    return suggestions


def _binary_install_hint(plat: PlatformInfo) -> str:
    auto_cmd = "cli-anything-acloudviewer install app"
    if IS_LINUX:
        tag = plat.ubuntu_tag or _closest_ubuntu_tag(plat.glibc_version)
        cuda = "cuda" if plat.has_nvidia_gpu else "cpu"
        return (
            f"Auto-install: {auto_cmd}\n"
            f"  Manual: download ACloudViewer-*-{tag}-{cuda}-amd64.run\n"
            f"    chmod +x *.run && ./*.run --root ~/ACloudViewer "
            f"--accept-licenses --accept-messages --confirm-command install\n"
            f"  Or set: export ACV_BINARY=/path/to/ACloudViewer"
        )
    elif IS_MACOS:
        return (
            f"Auto-install: {auto_cmd}\n"
            f"  Manual: download ACloudViewer-*-mac-cpu-ARM64.dmg\n"
            f"    Mount DMG and run the installer, or drag .app to /Applications.\n"
            f"  Or set: export ACV_BINARY=/path/to/ACloudViewer.app/Contents/MacOS/ACloudViewer"
        )
    elif IS_WINDOWS:
        return (
            f"Auto-install: {auto_cmd}\n"
            f"  Manual: download ACloudViewer-*-win-*.exe\n"
            f"    Run the installer; the binary will be found automatically.\n"
            f"  Or set: set ACV_BINARY=C:\\path\\to\\ACloudViewer.exe"
        )
    return f"Auto-install: {auto_cmd}\n  Manual: visit {HOMEPAGE}"


def format_check_report(status: dict) -> str:
    """Format check_installation() result as a human-readable report."""
    lines: list[str] = []
    p = status["platform"]
    lines.append("Platform:")
    lines.append(f"  OS:         {p['os']}")
    lines.append(f"  Arch:       {p['arch']}")
    lines.append(f"  Python:     {p['python']}")
    lines.append(f"  glibc:      {p['glibc']}")
    lines.append(f"  NVIDIA GPU: {'yes' if p['nvidia_gpu'] else 'no'}")
    lines.append("")

    b = status["binary"]
    mark = "\u2705" if b["found"] else "\u274c"
    lines.append(f"ACloudViewer Binary: {mark}")
    if b["found"]:
        lines.append(f"  Path:    {b['path']}")
        lines.append(f"  Version: {b['version'] or 'unknown'}")
    else:
        lines.append("  NOT FOUND — required for headless processing")

    lines.append("")
    cv = status["python_package"]
    mark = "\u2705" if cv["found"] else "\u26a0\ufe0f"
    lines.append(f"cloudViewer Python:  {mark}")
    if cv["found"]:
        lines.append(f"  Version: {cv['version']}")
    else:
        lines.append("  NOT INSTALLED (optional — for Python bindings)")

    lines.append("")
    ready = status["ready"]
    if ready:
        lines.append("\u2705 Ready to use!")
    else:
        lines.append("\u274c Not ready — install missing components:")
        for s in status.get("install_suggestions", []):
            lines.append(f"  \u2022 {s['component']} [{s['priority']}]")
            lines.append(f"    Auto:   {s['auto_install']}")
            lines.append(f"    Manual: {s['manual']}")
            if "details" in s:
                for detail_line in s["details"].split("\n"):
                    lines.append(f"    {detail_line}")

    return "\n".join(lines)
