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


# ── MCP client registration tests ────────────────────────────────────────

from cli_anything.acloudviewer.utils.installer import (
    ClientTarget,
    MCP_COMMAND,
    MCP_SERVER_KEY,
    detect_mcp_clients,
    mcp_server_entry,
    register_mcp_client,
    _upsert_json_mcp_server,
    _upsert_toml_mcp_server,
)

_HARNESS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)


def _run_cli(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _HARNESS_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "cli_anything.acloudviewer"] + args,
        capture_output=True, text=True, timeout=timeout, env=env)


class TestMcpClientRegistration:
    """install clients: detection, JSON/TOML upsert, .bak backups."""

    def test_mcp_server_entry_shape(self):
        entry = mcp_server_entry("headless")
        assert entry == {
            "type": "stdio",
            "command": MCP_COMMAND,
            "args": ["--mode", "headless"],
        }

    def test_mcp_server_entry_invalid_mode(self):
        with pytest.raises(InstallError):
            mcp_server_entry("bogus")

    def test_json_create_fresh_config(self, tmp_path):
        cfg = tmp_path / "claude.json"
        result = _upsert_json_mcp_server(cfg, mcp_server_entry("auto"))
        assert result["action"] == "created"
        assert result["backup"] is None
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["mcpServers"][MCP_SERVER_KEY]["command"] == MCP_COMMAND

    def test_json_merge_preserves_other_keys(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({"top": 1, "mcpServers": {"other": {"command": "x"}}}))
        result = _upsert_json_mcp_server(cfg, mcp_server_entry("auto"))
        assert result["action"] == "updated"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["top"] == 1
        assert data["mcpServers"]["other"] == {"command": "x"}
        assert data["mcpServers"][MCP_SERVER_KEY]["args"] == ["--mode", "auto"]
        backup = Path(result["backup"])
        assert backup.exists()
        backup_data = json.loads(backup.read_text(encoding="utf-8"))
        assert list(backup_data["mcpServers"].keys()) == ["other"]

    def test_json_unchanged_skips_backup(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        entry = mcp_server_entry("auto")
        _upsert_json_mcp_server(cfg, entry)
        result = _upsert_json_mcp_server(cfg, entry)
        assert result["action"] == "unchanged"
        assert result["backup"] is None
        assert not (tmp_path / "mcp.json.bak").exists()

    def test_json_invalid_config_aborts_without_destroying(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text("{not json", encoding="utf-8")
        with pytest.raises(InstallError):
            _upsert_json_mcp_server(cfg, mcp_server_entry("auto"))
        assert cfg.read_text(encoding="utf-8") == "{not json"

    def test_toml_append_fresh_config(self, tmp_path):
        cfg = tmp_path / "config.toml"
        result = _upsert_toml_mcp_server(cfg, "auto")
        assert result["action"] == "created"
        text = cfg.read_text(encoding="utf-8")
        assert f"[mcp_servers.{MCP_SERVER_KEY}]" in text
        assert f'command = "{MCP_COMMAND}"' in text
        assert 'args = ["--mode", "auto"]' in text

    def test_toml_replaces_only_own_section(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            '[mcp_servers.old]\ncommand = "x"\n\n'
            f"[mcp_servers.{MCP_SERVER_KEY}]\n"
            'command = "old"\nargs = ["--mode", "gui"]\n\n'
            '[profile]\nname = "p"\n',
            encoding="utf-8",
        )
        result = _upsert_toml_mcp_server(cfg, "headless")
        assert result["action"] == "updated"
        text = cfg.read_text(encoding="utf-8")
        assert 'args = ["--mode", "headless"]' in text
        assert 'args = ["--mode", "gui"]' not in text
        assert "[mcp_servers.old]" in text and 'command = "x"' in text
        assert "[profile]" in text and 'name = "p"' in text
        backup = Path(result["backup"])
        assert backup.exists()
        assert 'args = ["--mode", "gui"]' in backup.read_text(encoding="utf-8")

    def test_toml_unchanged_skips_backup(self, tmp_path):
        cfg = tmp_path / "config.toml"
        _upsert_toml_mcp_server(cfg, "auto")
        result = _upsert_toml_mcp_server(cfg, "auto")
        assert result["action"] == "unchanged"
        assert result["backup"] is None

    def test_detect_covers_four_clients(self, tmp_path):
        with patch("cli_anything.acloudviewer.utils.installer.Path.home",
                   return_value=tmp_path), \
             patch("cli_anything.acloudviewer.utils.installer.shutil.which",
                   return_value=None):
            targets = detect_mcp_clients()
        assert {t.key for t in targets} == {"claude-code", "claude-desktop", "codex", "cursor"}
        assert all(not t.detected for t in targets)

    def test_register_json_client_end_to_end(self, tmp_path):
        target = ClientTarget(key="cursor", title="Cursor",
                              config_path=tmp_path / "mcp.json",
                              detected=True, detail="test")
        result = register_mcp_client(target, mode="auto")
        assert result["action"] == "created" and result["client"] == "cursor"
        data = json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))
        assert data["mcpServers"][MCP_SERVER_KEY]["command"] == MCP_COMMAND

    def test_register_skipped_without_config_path(self):
        target = ClientTarget(key="claude-desktop", title="Claude Desktop",
                              config_path=None, detected=False, detail="no APPDATA")
        result = register_mcp_client(target, mode="auto")
        assert result["action"] == "skipped"

    def test_register_dry_run_writes_nothing(self, tmp_path):
        target = ClientTarget(key="codex", title="Codex CLI",
                              config_path=tmp_path / "config.toml",
                              detected=True, detail="test")
        result = register_mcp_client(target, mode="auto", dry_run=True)
        assert result["action"] == "dry-run"
        assert not (tmp_path / "config.toml").exists()


class TestInstallClientsCLI:
    """CLI wiring: dry-run must not touch the filesystem."""

    def test_dry_run_json(self):
        r = _run_cli(["--json", "install", "clients", "--dry-run", "--client", "cursor"])
        assert r.returncode == 0, r.stdout + r.stderr
        data = json.loads(r.stdout)
        assert data["dry_run"] is True
        assert data["mode"] == "auto"
        assert len(data["clients"]) == 1
        assert data["clients"][0]["action"] == "dry-run"
        assert data["clients"][0]["client"] == "cursor"

    def test_non_interactive_guard(self):
        r = _run_cli(["install", "clients"])
        combined = r.stdout + r.stderr
        assert "--all" in combined
        assert "Non-interactive" in combined


# ── MCP client removal tests ─────────────────────────────────────────────

from cli_anything.acloudviewer.utils.installer import (
    _remove_json_mcp_server,
    _remove_toml_mcp_server,
    remove_mcp_client,
)


class TestMcpClientRemoval:
    """install clients --remove: symmetric undo with .bak backups."""

    def test_json_remove_ours_only(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({
            "top": 1,
            "mcpServers": {
                "other": {"command": "x"},
                MCP_SERVER_KEY: {"command": MCP_COMMAND, "args": ["--mode", "auto"]},
            },
        }))
        result = _remove_json_mcp_server(cfg)
        assert result["action"] == "removed"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["top"] == 1
        assert list(data["mcpServers"].keys()) == ["other"]
        backup = json.loads(Path(result["backup"]).read_text(encoding="utf-8"))
        assert backup["mcpServers"][MCP_SERVER_KEY]["command"] == MCP_COMMAND

    def test_json_remove_absent(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        result = _remove_json_mcp_server(cfg)
        assert result["action"] == "absent" and result["backup"] is None
        assert json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]["other"] == {"command": "x"}

    def test_json_remove_conflict_keeps_foreign_entry(self, tmp_path):
        cfg = tmp_path / "mcp.json"
        original = json.dumps({"mcpServers": {
            MCP_SERVER_KEY: {"command": "someone-else"}}})
        cfg.write_text(original)
        result = _remove_json_mcp_server(cfg)
        assert result["action"] == "conflict"
        assert cfg.read_text(encoding="utf-8") == original

    def test_toml_remove_section(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            '[mcp_servers.old]\ncommand = "x"\n\n'
            f"[mcp_servers.{MCP_SERVER_KEY}]\n"
            f'command = "{MCP_COMMAND}"\n\n'
            '[profile]\nname = "p"\n',
            encoding="utf-8",
        )
        result = _remove_toml_mcp_server(cfg)
        assert result["action"] == "removed"
        text = cfg.read_text(encoding="utf-8")
        assert MCP_SERVER_KEY not in text
        assert "[mcp_servers.old]" in text and "[profile]" in text
        assert f'command = "{MCP_COMMAND}"' in Path(result["backup"]).read_text(encoding="utf-8")

    def test_toml_remove_absent(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('[mcp_servers.old]\ncommand = "x"\n', encoding="utf-8")
        result = _remove_toml_mcp_server(cfg)
        assert result["action"] == "absent" and result["backup"] is None
        assert "[mcp_servers.old]" in cfg.read_text(encoding="utf-8")

    def test_remove_client_dry_run_and_absent(self, tmp_path):
        target = ClientTarget(key="cursor", title="Cursor",
                              config_path=tmp_path / "missing.json",
                              detected=False, detail="test")
        assert remove_mcp_client(target, dry_run=True)["action"] == "dry-run"
        assert remove_mcp_client(target)["action"] == "absent"


# ── Source-build plan tests ──────────────────────────────────────────────

from cli_anything.acloudviewer.utils.source_builder import (
    BuildPlan, BuildStep, SourceBuildError, run_source_build,
    plan_source_build, verify_build,
)


class TestSourceBuilderPlans:
    """One command = clone + env + configure + build; presets mirror the guides."""

    def test_linux_plan_uses_repo_one_click_script(self, tmp_path):
        plan = plan_source_build(platform="linux", source_dir=tmp_path,
                                 prefix=tmp_path / "install", jobs=8)
        assert plan.platform == "linux"
        assert len(plan.steps) == 1
        argv = " ".join(plan.steps[0].argv)
        assert "setup_and_build_acloudviewer_linux.sh" in argv
        assert "--jobs 8" in argv and str(tmp_path) in argv
        # conda is deliberately not part of the Linux preset
        assert "conda" not in argv

    def test_linux_skip_build_passthrough(self, tmp_path):
        plan = plan_source_build(platform="linux", source_dir=tmp_path,
                                 skip_build=True)
        assert "--skip-build" in " ".join(plan.steps[0].argv)

    def test_macos_plan_matches_guide(self, tmp_path):
        plan = plan_source_build(platform="macos", source_dir=tmp_path,
                                 prefix=tmp_path / "install")
        argv_all = " ".join(" ".join(s.argv) for s in plan.steps)
        assert "conda_macos_cloudViewer.yml" in argv_all
        assert "conda run -n cloudViewer" in argv_all
        assert "-DBUILD_WITH_CONDA=ON" in argv_all
        assert "-DPLUGIN_STANDARD_QSIBR=OFF" in argv_all
        assert "-DAICore_USE_VULKAN=ON" not in argv_all   # macOS uses Metal
        names = [s.name for s in plan.steps]
        assert any("conda env" in n for n in names)
        assert any("configure" in n for n in names)
        assert any("build" in n for n in names)

    def test_macos_skip_env_drops_env_steps(self, tmp_path):
        plan = plan_source_build(platform="macos", source_dir=tmp_path,
                                 skip_env=True)
        assert not any("conda env" in s.name for s in plan.steps)

    def test_windows_plan_matches_guide(self, tmp_path):
        plan = plan_source_build(platform="windows", source_dir=tmp_path,
                                 prefix=tmp_path / "install")
        argv_all = " ".join(" ".join(s.argv) for s in plan.steps)
        assert "conda_windows_cloudViewer.yml" in argv_all
        assert "setup_conda_env.ps1" in argv_all
        assert "Visual Studio 17 2022" in argv_all
        assert "-DBUILD_CUDA_MODULE=ON" in argv_all
        assert "-DAICore_USE_VULKAN=ON" in argv_all
        # configure must run in the SAME shell that sourced setup_conda_env.ps1
        configure = next(s for s in plan.steps if "configure" in s.name)
        assert "setup_conda_env.ps1" in " ".join(configure.argv)
        assert "conda run" in " ".join(configure.argv)

    def test_windows_cpu_only_flips_cuda(self, tmp_path):
        plan = plan_source_build(platform="windows", source_dir=tmp_path,
                                 cpu_only=True)
        argv_all = " ".join(" ".join(s.argv) for s in plan.steps)
        assert "-DBUILD_CUDA_MODULE=OFF" in argv_all
        assert "-DAICore_BUNDLE_CUDA_RUNTIME=OFF" in argv_all

    def test_unknown_platform_rejected(self, tmp_path):
        with pytest.raises(SourceBuildError):
            plan_source_build(platform="solaris", source_dir=tmp_path)


class TestSourceBuilderRun:
    def test_run_executes_steps_in_order(self, tmp_path):
        calls = []

        def runner(argv, cwd=None, timeout=None):
            calls.append(argv[0])
            return subprocess.CompletedProcess(argv, 0, "", "")

        plan = BuildPlan(platform="linux", source_dir=tmp_path,
                         build_dir=tmp_path / "b", prefix=tmp_path / "p",
                         steps=[BuildStep(name="a", argv=["a"]),
                                BuildStep(name="b", argv=["b"])])
        results = run_source_build(plan, runner=runner, echo=lambda *_: None)
        assert calls == ["a", "b"]
        assert all(r["exit_code"] == 0 for r in results)

    def test_dry_run_executes_nothing(self, tmp_path):
        def runner(*_a, **_k):
            raise AssertionError("runner must not be called in dry-run")

        plan = BuildPlan(platform="linux", source_dir=tmp_path,
                         build_dir=tmp_path / "b", prefix=tmp_path / "p",
                         steps=[BuildStep(name="a", argv=["a"])])
        results = run_source_build(plan, runner=runner, echo=lambda *_: None,
                                   dry_run=True)
        assert results[0]["action"] == "dry-run"

    def test_optional_failure_continues_required_fails(self, tmp_path):
        responses = {"opt": 1, "req": 0}

        def runner(argv, cwd=None, timeout=None):
            return subprocess.CompletedProcess(argv, responses[argv[0]], "", "")

        plan = BuildPlan(platform="linux", source_dir=tmp_path,
                         build_dir=tmp_path / "b", prefix=tmp_path / "p",
                         steps=[BuildStep(name="opt", argv=["opt"], optional=True),
                                BuildStep(name="req", argv=["req"])])
        results = run_source_build(plan, runner=runner, echo=lambda *_: None)
        assert results[0]["exit_code"] == 1 and results[1]["exit_code"] == 0

        plan2 = BuildPlan(platform="linux", source_dir=tmp_path,
                          build_dir=tmp_path / "b", prefix=tmp_path / "p",
                          steps=[BuildStep(name="req", argv=["req"], optional=False)])
        responses["req"] = 2
        with pytest.raises(SourceBuildError):
            run_source_build(plan2, runner=runner, echo=lambda *_: None)

    def test_verify_build_finds_binary(self, tmp_path):
        build_dir = tmp_path / "build_app" / "bin"
        build_dir.mkdir(parents=True)
        (build_dir / "ACloudViewer").write_text("#!/bin/sh\n")
        plan = BuildPlan(platform="linux", source_dir=tmp_path,
                         build_dir=tmp_path / "build_app",
                         prefix=tmp_path / "install")
        assert verify_build(plan) == str(build_dir / "ACloudViewer")


# ── doctor / install models helpers ──────────────────────────────────────

from cli_anything.acloudviewer.acloudviewer_cli import (
    _probe_download_support, _probe_rpc,
)
from cli_anything.acloudviewer.utils.acloudviewer_backend import BackendError


class TestProbeDownloadSupport:
    """The DOWNLOAD parser probe classifies binary error shapes."""

    @staticmethod
    def _backend(message):
        backend = MagicMock()
        if message is None:
            backend.ai_run.return_value = {"succeeded": 0}
        else:
            backend.ai_run.side_effect = BackendError(message)
        return backend

    def test_prepare_command_accepts_token(self):
        # Parser accepted DOWNLOAD and failed later on the missing OUT_DIR.
        backend = self._backend(
            "QUERY_SPLAT returned no RESULT_JSON: [QUERY_SPLAT] -QUERY_SPLAT "
            "needs OUT_DIR <dir>")
        assert _probe_download_support(backend, "querysplat") is True

    def test_bridge_command_rejects_token(self):
        backend = self._backend(
            "MAP_ANYTHING_RECONSTRUCT returned no RESULT_JSON: Unknown "
            "argument after -MAP_ANYTHING_RECONSTRUCT: DOWNLOAD")
        assert _probe_download_support(backend, "map-anything") is False

    def test_missing_task_is_surfaced_not_judged(self):
        backend = self._backend(
            "/opt/ACloudViewer does not provide -RMBG_REMOVE (its rmbg "
            "plugin is missing or too old)")
        with pytest.raises(BackendError):
            _probe_download_support(backend, "rmbg")


class TestProbeRpc:
    def test_reachable(self):
        with patch("cli_anything.acloudviewer.utils.rpc_client."
                   "ACloudViewerRPCClient") as mock_client:
            mock_client.return_value.ping.return_value = "pong"
            mock_client.return_value.list_methods.return_value = [1, 2, 3]
            result = _probe_rpc("ws://127.0.0.1:6001", 5)
        assert result["reachable"] is True
        assert result["methods"] == 3

    def test_unreachable_is_reported_not_raised(self):
        with patch("cli_anything.acloudviewer.utils.rpc_client."
                   "ACloudViewerRPCClient", side_effect=OSError("refused")):
            result = _probe_rpc("ws://127.0.0.1:6001", 5)
        assert result["reachable"] is False
        assert "OSError" in result["error"]


class TestNewCLICommands:
    """CLI wiring for install source/models/clients --remove and doctor."""

    def test_install_source_dry_run(self):
        r = _run_cli(["--json", "install", "source", "--dry-run",
                      "--dir", str(Path(tempfile.mkdtemp()))])
        assert r.returncode == 0, r.stdout + r.stderr
        data = json.loads(r.stdout)
        assert data["platform"] in ("linux", "macos", "windows")
        assert isinstance(data["steps"], list) and data["steps"]

    def test_install_models_list_requires_no_binary_but_reports(self):
        # The matrix probes the DOWNLOAD parser per task; without a usable
        # binary every row reports an error instead of pretending success.
        r = _run_cli(["--json", "install", "models", "--list"])
        assert r.returncode == 0, r.stdout + r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list) and data
        assert {"task", "command", "headless_prefetch"} <= set(data[0].keys())

    def test_install_clients_remove_dry_run(self):
        r = _run_cli(["--json", "install", "clients", "--remove", "--dry-run",
                      "--client", "cursor"])
        assert r.returncode == 0, r.stdout + r.stderr
        data = json.loads(r.stdout)
        assert data["remove"] is True
        assert data["clients"][0]["action"] == "dry-run"

    def test_doctor_json(self):
        r = _run_cli(["--json", "doctor", "--skip-rpc"])
        assert r.returncode == 0, r.stdout + r.stderr
        data = json.loads(r.stdout)
        assert {"installation", "rpc", "ai_registry", "verdict"} <= set(data.keys())
        assert data["rpc"]["skipped"] is True
        assert data["ai_registry"]["tasks"] >= 17

    def test_doctor_help(self):
        r = _run_cli(["doctor", "--help"])
        assert r.returncode == 0
        assert "--skip-rpc" in r.stdout

    def test_install_source_help(self):
        r = _run_cli(["install", "source", "--help"])
        assert r.returncode == 0
        for flag in ["--dry-run", "--branch", "--jobs", "--cpu-only",
                     "--skip-build", "--prefix"]:
            assert flag in r.stdout

    def test_install_models_help(self):
        r = _run_cli(["install", "models", "--help"])
        assert r.returncode == 0
        for flag in ["--task", "--list", "--image", "--out-dir"]:
            assert flag in r.stdout
