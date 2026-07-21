"""Unit tests for installer module — fully mocked, no network or binary needed."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from cli_anything.acloudviewer.utils.installer import (
    PlatformInfo,
    ReleaseAsset,
    ReleaseInfo,
    InstallError,
    detect_platform,
    fetch_releases,
    get_latest_release,
    find_matching_wheel,
    find_matching_app,
    check_installation,
    format_check_report,
    _closest_ubuntu_tag,
    _detect_linux_distro,
    _detect_glibc_version,
    _detect_nvidia_gpu,
    _find_binary_in_dir,
    _download_with_progress,
    IS_MACOS,
    IS_WINDOWS,
    install_wheel,
    install_app,
    HOMEPAGE,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

def _make_platform(
    os_name="linux", os_id="ubuntu", os_version="20.04",
    arch="x86_64", python_version=(3, 11), glibc_version="2.31",
    has_nvidia_gpu=True,
) -> PlatformInfo:
    return PlatformInfo(
        os_name=os_name, os_id=os_id, os_version=os_version,
        arch=arch, python_version=python_version,
        glibc_version=glibc_version, has_nvidia_gpu=has_nvidia_gpu,
    )


def _make_release(tag="v3.9.4", prerelease=False, assets=None):
    return ReleaseInfo(
        tag=tag,
        name=f"ACloudViewer {tag}",
        prerelease=prerelease,
        published_at="2025-10-14",
        assets=assets or [],
    )


def _make_asset(name, size=100_000_000):
    return ReleaseAsset(
        name=name,
        download_url=f"https://github.com/Asher-1/ACloudViewer/releases/download/v3.9.4/{name}",
        size=size,
    )


SAMPLE_ASSETS = [
    _make_asset("ACloudViewer-3.9.4-ubuntu20.04-cpu-amd64.run", 244_000_000),
    _make_asset("ACloudViewer-3.9.4-ubuntu20.04-cuda-amd64.run", 417_000_000),
    _make_asset("ACloudViewer-3.9.4-ubuntu22.04-cpu-amd64.run", 247_000_000),
    _make_asset("ACloudViewer-3.9.4-ubuntu22.04-cuda-amd64.run", 419_000_000),
    _make_asset("ACloudViewer-3.9.4-mac-cpu-ARM64.dmg", 244_000_000),
    _make_asset("ACloudViewer-3.9.4-win-cpu-amd64.exe", 105_000_000),
    _make_asset("ACloudViewer-3.9.4-win-cuda-amd64.exe", 161_000_000),
    _make_asset("cloudviewer-3.9.4-cp310-cp310-manylinux_2_31_x86_64.whl", 497_000_000),
    _make_asset("cloudviewer-3.9.4-cp311-cp311-manylinux_2_31_x86_64.whl", 498_000_000),
    _make_asset("cloudviewer-3.9.4-cp311-cp311-manylinux_2_35_x86_64.whl", 502_000_000),
    _make_asset("cloudviewer-3.9.4-cp312-cp312-manylinux_2_31_x86_64.whl", 500_000_000),
    _make_asset("cloudviewer-3.9.4-cp311-cp311-macosx_14_0_arm64.whl", 127_000_000),
    _make_asset("cloudviewer-3.9.4-cp311-cp311-win_amd64.whl", 335_000_000),
    _make_asset("cloudviewer_cpu-3.9.4-cp311-cp311-manylinux_2_31_x86_64.whl", 139_000_000),
    _make_asset("cloudviewer_cpu-3.9.4-cp311-cp311-manylinux_2_35_x86_64.whl", 142_000_000),
    _make_asset("cloudviewer_cpu-3.9.4-cp311-cp311-win_amd64.whl", 174_000_000),
]


# ── PlatformInfo tests ───────────────────────────────────────────────────

class TestPlatformInfo:
    def test_python_tag(self):
        p = _make_platform(python_version=(3, 11))
        assert p.python_tag == "cp311"

    def test_python_tag_310(self):
        p = _make_platform(python_version=(3, 10))
        assert p.python_tag == "cp310"

    def test_ubuntu_tag(self):
        p = _make_platform(os_id="ubuntu", os_version="22.04")
        assert p.ubuntu_tag == "ubuntu22.04"

    def test_ubuntu_tag_non_ubuntu(self):
        p = _make_platform(os_id="centos", os_version="8")
        assert p.ubuntu_tag == ""

    def test_manylinux_tag(self):
        p = _make_platform(glibc_version="2.31", arch="x86_64")
        assert p.manylinux_tag == "manylinux_2_31_x86_64"

    def test_manylinux_tag_arm(self):
        p = _make_platform(glibc_version="2.35", arch="aarch64")
        assert p.manylinux_tag == "manylinux_2_35_aarch64"

    def test_manylinux_tag_empty_glibc(self):
        p = _make_platform(glibc_version="")
        assert p.manylinux_tag == ""

    def test_arch_tag_x86(self):
        p = _make_platform(arch="x86_64")
        assert p.arch_tag == "amd64"

    def test_arch_tag_arm(self):
        p = _make_platform(arch="arm64")
        assert p.arch_tag == "ARM64"

    def test_size_mb(self):
        a = _make_asset("test.whl", 104_857_600)
        assert a.size_mb == 100.0

    def test_release_version(self):
        r = _make_release(tag="v3.9.4")
        assert r.version == "3.9.4"

    def test_release_label_stable(self):
        r = _make_release(tag="v3.9.4", prerelease=False)
        assert "stable" in r.label

    def test_release_label_beta(self):
        r = _make_release(tag="main-devel", prerelease=True)
        assert "beta" in r.label


# ── Closest Ubuntu tag ───────────────────────────────────────────────────

class TestClosestUbuntuTag:
    def test_exact_2_31(self):
        assert _closest_ubuntu_tag("2.31") == "ubuntu20.04"

    def test_exact_2_35(self):
        assert _closest_ubuntu_tag("2.35") == "ubuntu22.04"

    def test_exact_2_39(self):
        assert _closest_ubuntu_tag("2.39") == "ubuntu24.04"

    def test_exact_2_27(self):
        assert _closest_ubuntu_tag("2.27") == "ubuntu18.04"

    def test_between_2_32(self):
        assert _closest_ubuntu_tag("2.32") == "ubuntu20.04"

    def test_very_old(self):
        assert _closest_ubuntu_tag("2.17") == "ubuntu18.04"

    def test_very_new(self):
        assert _closest_ubuntu_tag("2.40") == "ubuntu24.04"

    def test_invalid(self):
        assert _closest_ubuntu_tag("") == "ubuntu20.04"


# ── Platform detection helpers ───────────────────────────────────────────

class TestDetectLinuxDistro:
    def test_reads_os_release(self, tmp_path):
        os_release = tmp_path / "os-release"
        os_release.write_text('ID=ubuntu\nVERSION_ID="22.04"\n')
        with patch("builtins.open", return_value=os_release.open()):
            os_id, ver = _detect_linux_distro()
            assert os_id == "ubuntu"
            assert ver == "22.04"

    def test_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            os_id, ver = _detect_linux_distro()
            assert os_id == "unknown"
            assert ver == ""


class TestDetectGlibcVersion:
    def test_parses_ldd_output(self):
        with patch("subprocess.check_output",
                    return_value="ldd (Ubuntu GLIBC 2.31-0ubuntu9) 2.31\n"):
            assert _detect_glibc_version() == "2.31"

    def test_handles_error(self):
        with patch("subprocess.check_output", side_effect=FileNotFoundError):
            assert _detect_glibc_version() == ""


class TestDetectNvidiaGpu:
    def test_found(self):
        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
            assert _detect_nvidia_gpu() is True

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            assert _detect_nvidia_gpu() is False


# ── Wheel matching ───────────────────────────────────────────────────────

class TestFindMatchingWheel:
    def _release(self):
        return _make_release(assets=SAMPLE_ASSETS)

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_gpu_exact_match(self):
        plat = _make_platform(python_version=(3, 11), glibc_version="2.31")
        w = find_matching_wheel(self._release(), plat, cpu_only=False)
        assert w is not None
        assert w.name == "cloudviewer-3.9.4-cp311-cp311-manylinux_2_31_x86_64.whl"

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_cpu_only(self):
        plat = _make_platform(python_version=(3, 11), glibc_version="2.31")
        w = find_matching_wheel(self._release(), plat, cpu_only=True)
        assert w is not None
        assert "cloudviewer_cpu-" in w.name
        assert "cp311" in w.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_fallback_to_compatible(self):
        plat = _make_platform(python_version=(3, 11), glibc_version="2.33")
        w = find_matching_wheel(self._release(), plat, cpu_only=False)
        assert w is not None
        assert "cp311" in w.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_no_match_wrong_python(self):
        plat = _make_platform(python_version=(3, 8), glibc_version="2.31")
        w = find_matching_wheel(self._release(), plat, cpu_only=False)
        assert w is None

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_macos_arm(self):
        plat = _make_platform(os_name="darwin", os_id="macos", arch="arm64",
                              python_version=(3, 11), glibc_version="")
        w = find_matching_wheel(self._release(), plat)
        assert w is not None
        assert "macosx" in w.name
        assert "arm64" in w.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", True)
    def test_windows(self):
        plat = _make_platform(os_name="windows", os_id="windows", arch="x86_64",
                              python_version=(3, 11), glibc_version="")
        w = find_matching_wheel(self._release(), plat)
        assert w is not None
        assert "win_amd64" in w.name


# ── App matching ─────────────────────────────────────────────────────────

class TestFindMatchingApp:
    def _release(self):
        return _make_release(assets=SAMPLE_ASSETS)

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_cuda(self):
        plat = _make_platform()
        a = find_matching_app(self._release(), plat, cpu_only=False)
        assert a is not None
        assert "ubuntu20.04" in a.name
        assert "-cuda-" in a.name
        assert a.name.endswith(".run")

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_cpu_only(self):
        plat = _make_platform()
        a = find_matching_app(self._release(), plat, cpu_only=True)
        assert a is not None
        assert "-cpu-" in a.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_22_04(self):
        plat = _make_platform(os_version="22.04", glibc_version="2.35")
        a = find_matching_app(self._release(), plat, cpu_only=True)
        assert a is not None
        assert "ubuntu22.04" in a.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_linux_cuda_fallback_to_cpu(self):
        assets = [_make_asset("ACloudViewer-3.9.4-ubuntu20.04-cpu-amd64.run")]
        release = _make_release(assets=assets)
        plat = _make_platform()
        a = find_matching_app(release, plat, cpu_only=False)
        assert a is not None
        assert "-cpu-" in a.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", True)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", False)
    def test_macos(self):
        plat = _make_platform(os_name="darwin", os_id="macos", arch="arm64",
                              glibc_version="")
        a = find_matching_app(self._release(), plat)
        assert a is not None
        assert a.name.endswith(".dmg")
        assert "ARM64" in a.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", True)
    def test_windows_cuda(self):
        plat = _make_platform(os_name="windows", os_id="windows", arch="x86_64",
                              glibc_version="")
        a = find_matching_app(self._release(), plat, cpu_only=False)
        assert a is not None
        assert a.name.endswith(".exe")
        assert "-cuda-" in a.name

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_MACOS", False)
    @patch("cli_anything.acloudviewer.utils.installer.IS_WINDOWS", True)
    def test_windows_cpu(self):
        plat = _make_platform(os_name="windows", os_id="windows", arch="x86_64",
                              glibc_version="")
        a = find_matching_app(self._release(), plat, cpu_only=True)
        assert a is not None
        assert "-cpu-" in a.name


# ── fetch_releases ───────────────────────────────────────────────────────

class TestFetchReleases:
    def _mock_response(self, data):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_parses_releases(self):
        api_data = [{
            "tag_name": "v3.9.4",
            "name": "ACloudViewer 3.9.4",
            "prerelease": False,
            "published_at": "2025-10-14",
            "assets": [{
                "name": "test.whl",
                "browser_download_url": "https://example.com/test.whl",
                "size": 1000,
            }],
        }]
        with patch("urllib.request.urlopen", return_value=self._mock_response(api_data)):
            releases = fetch_releases()
            assert len(releases) == 1
            assert releases[0].tag == "v3.9.4"
            assert len(releases[0].assets) == 1

    def test_filters_prerelease(self):
        api_data = [
            {"tag_name": "main-devel", "prerelease": True, "assets": []},
            {"tag_name": "v3.9.4", "prerelease": False, "assets": []},
        ]
        with patch("urllib.request.urlopen", return_value=self._mock_response(api_data)):
            releases = fetch_releases(include_prerelease=False)
            assert len(releases) == 1
            assert releases[0].tag == "v3.9.4"

    def test_network_error(self):
        import urllib.error
        with patch("urllib.request.urlopen",
                    side_effect=urllib.error.URLError("timeout")):
            with pytest.raises(InstallError, match="Cannot reach"):
                fetch_releases()


class TestGetLatestRelease:
    def _mock_releases(self):
        return [
            _make_release(tag="main-devel", prerelease=True),
            _make_release(tag="v3.9.4", prerelease=False),
            _make_release(tag="v3.9.3", prerelease=False),
        ]

    def test_any_returns_first(self):
        with patch("cli_anything.acloudviewer.utils.installer.fetch_releases",
                    return_value=self._mock_releases()):
            r = get_latest_release(channel="any")
            assert r.tag == "main-devel"

    def test_stable_skips_prerelease(self):
        with patch("cli_anything.acloudviewer.utils.installer.fetch_releases",
                    return_value=self._mock_releases()):
            r = get_latest_release(channel="stable")
            assert r.tag == "v3.9.4"

    def test_beta_returns_prerelease(self):
        with patch("cli_anything.acloudviewer.utils.installer.fetch_releases",
                    return_value=self._mock_releases()):
            r = get_latest_release(channel="beta")
            assert r.tag == "main-devel"

    def test_no_stable_raises(self):
        releases = [_make_release(tag="main-devel", prerelease=True)]
        with patch("cli_anything.acloudviewer.utils.installer.fetch_releases",
                    return_value=releases):
            with pytest.raises(InstallError, match="No stable"):
                get_latest_release(channel="stable")


# ── _find_binary_in_dir ──────────────────────────────────────────────────

class TestFindBinaryInDir:
    def test_finds_script(self, tmp_path):
        # Create platform-appropriate binary file
        if IS_MACOS:
            binary_name = "ACloudViewer"
        elif IS_WINDOWS:
            binary_name = "ACloudViewer.exe"
        else:  # Linux
            binary_name = "ACloudViewer.sh"
        
        (tmp_path / binary_name).write_text("#!/bin/sh" if not IS_WINDOWS else "@echo off")
        result = _find_binary_in_dir(tmp_path)
        assert result is not None
        assert result.name == binary_name

    def test_finds_in_subdir(self, tmp_path):
        sub = tmp_path / "bin"
        sub.mkdir()
        
        # Create platform-appropriate binary file
        if IS_MACOS:
            binary_name = "ACloudViewer"
        elif IS_WINDOWS:
            binary_name = "ACloudViewer.exe"
        else:  # Linux
            binary_name = "ACloudViewer.sh"
        
        (sub / binary_name).write_text("#!/bin/sh" if not IS_WINDOWS else "@echo off")
        result = _find_binary_in_dir(tmp_path)
        assert result is not None

    def test_not_found(self, tmp_path):
        assert _find_binary_in_dir(tmp_path) is None


# ── check_installation ───────────────────────────────────────────────────

class TestCheckInstallation:
    @patch("cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerBackend.get_version",
           return_value=None)
    @patch("cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerBackend.find_binary",
           return_value=None)
    @patch("cli_anything.acloudviewer.utils.installer._get_cloudviewer_version",
           return_value=None)
    @patch("cli_anything.acloudviewer.utils.installer.detect_platform",
           return_value=_make_platform())
    def test_missing_binary(self, mock_plat, mock_cv, mock_find, mock_ver):
        status = check_installation()
        assert status["binary"]["found"] is False
        assert status["ready"] is False
        assert len(status["install_suggestions"]) >= 1

    @patch("cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerBackend.get_version",
           return_value="3.9.4")
    @patch("cli_anything.acloudviewer.utils.acloudviewer_backend.ACloudViewerBackend.find_binary",
           return_value="/usr/bin/ACloudViewer")
    @patch("cli_anything.acloudviewer.utils.installer._get_cloudviewer_version",
           return_value=None)
    @patch("cli_anything.acloudviewer.utils.installer.detect_platform",
           return_value=_make_platform())
    def test_binary_found(self, mock_plat, mock_cv, mock_find, mock_ver):
        status = check_installation()
        assert status["binary"]["found"] is True
        assert status["binary"]["path"] == "/usr/bin/ACloudViewer"
        assert status["ready"] is True


# ── format_check_report ──────────────────────────────────────────────────

class TestFormatCheckReport:
    def test_ready_report(self):
        status = {
            "platform": {"os": "ubuntu 20.04", "arch": "x86_64",
                         "python": "3.11", "glibc": "2.31", "nvidia_gpu": True},
            "binary": {"found": True, "path": "/usr/bin/ACloudViewer",
                       "version": "3.9.4"},
            "python_package": {"found": True, "version": "3.9.4"},
            "ready": True,
        }
        report = format_check_report(status)
        assert "Ready to use" in report
        assert "ubuntu 20.04" in report

    def test_not_ready_report(self):
        status = {
            "platform": {"os": "ubuntu 20.04", "arch": "x86_64",
                         "python": "3.11", "glibc": "2.31", "nvidia_gpu": False},
            "binary": {"found": False, "path": None, "version": None},
            "python_package": {"found": False, "version": None},
            "ready": False,
            "install_suggestions": [
                {"component": "ACloudViewer binary", "priority": "required",
                 "auto_install": "install app", "manual": "download"},
            ],
        }
        report = format_check_report(status)
        assert "Not ready" in report
        assert "install app" in report


# ── Download function ────────────────────────────────────────────────────

class TestDownloadWithProgress:
    @patch("shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    def test_prefers_curl(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        dest = tmp_path / "test.run"
        _download_with_progress("https://example.com/test.run", dest)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/curl"
        assert "-L" in cmd

    @patch("shutil.which", side_effect=lambda x: "/usr/bin/wget" if x == "wget" else None)
    @patch("subprocess.run")
    def test_falls_back_to_wget(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        dest = tmp_path / "test.run"
        _download_with_progress("https://example.com/test.run", dest)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/usr/bin/wget"

    @patch("shutil.which", return_value="/usr/bin/curl")
    @patch("subprocess.run")
    def test_curl_failure_raises(self, mock_run, mock_which, tmp_path):
        mock_run.return_value = MagicMock(returncode=1)
        dest = tmp_path / "test.run"
        with pytest.raises(InstallError, match="curl download failed"):
            _download_with_progress("https://example.com/test.run", dest)


# ── install_wheel ────────────────────────────────────────────────────────

class TestInstallWheel:
    @patch("cli_anything.acloudviewer.utils.installer._get_cloudviewer_version",
           return_value="3.9.4")
    @patch("subprocess.run")
    @patch("cli_anything.acloudviewer.utils.installer._download_with_progress")
    def test_success(self, mock_dl, mock_run, mock_ver):
        mock_run.return_value = MagicMock(returncode=0)
        asset = _make_asset("cloudviewer-3.9.4-cp311-cp311-manylinux_2_31_x86_64.whl")
        result = install_wheel(asset)
        assert result["status"] == "installed"
        assert result["version"] == "3.9.4"

    @patch("subprocess.run")
    @patch("cli_anything.acloudviewer.utils.installer._download_with_progress")
    def test_pip_failure(self, mock_dl, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error: conflict")
        asset = _make_asset("test.whl")
        with pytest.raises(InstallError, match="pip install failed"):
            install_wheel(asset)


# ── install_app ──────────────────────────────────────────────────────────

class TestInstallApp:
    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer._find_binary_in_dir")
    @patch("subprocess.run")
    @patch("cli_anything.acloudviewer.utils.installer._download_with_progress")
    def test_linux_extract_success(self, mock_dl, mock_run, mock_find, tmp_path):
        def create_fake_file(url, dest, **kw):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"#!/bin/sh\nfake")
            return dest
        mock_dl.side_effect = create_fake_file
        mock_run.return_value = MagicMock(returncode=0)
        mock_find.return_value = tmp_path / "bin" / "ACloudViewer.sh"

        asset = _make_asset("ACloudViewer-3.9.4-ubuntu20.04-cpu-amd64.run")
        result = install_app(asset, install_dir=tmp_path)
        assert result["status"] == "installed"
        assert "binary" in result

    @patch("cli_anything.acloudviewer.utils.installer.IS_LINUX", True)
    @patch("cli_anything.acloudviewer.utils.installer._find_binary_in_dir",
           return_value=None)
    @patch("subprocess.run")
    @patch("cli_anything.acloudviewer.utils.installer._download_with_progress")
    def test_linux_extract_fails_returns_failure(self, mock_dl, mock_run, mock_find, tmp_path):
        def create_fake_file(url, dest, **kw):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"#!/bin/sh\nfake")
            return dest
        mock_dl.side_effect = create_fake_file
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        asset = _make_asset("ACloudViewer-3.9.4-ubuntu20.04-cpu-amd64.run")
        result = install_app(asset, install_dir=tmp_path)
        assert result["status"] == "failed"
        assert "message" in result
