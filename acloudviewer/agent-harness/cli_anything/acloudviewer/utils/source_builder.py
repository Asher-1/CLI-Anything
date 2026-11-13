"""Source-build presets driven by docs/guides/compiling_doc.

One command = clone + platform environment + configure + build + install:

- Linux:   apt deps + pyenv via the repository's own idempotent one-click
           script (docs/guides/compiling_doc/setup_and_build_acloudviewer_linux.sh).
           Conda is deliberately NOT used on Linux (distribution packaging
           conflicts); the script implements Option A of
           compiling-cloudviewer-linux.md.
- macOS:   conda env from .ci/conda_macos_cloudViewer.yml, then cmake with
           -DBUILD_WITH_CONDA=ON (compiling-cloudviewer-macos.md).
- Windows: conda env from .ci/conda_windows_cloudViewer.yml, then
           scripts/setup_conda_env.ps1 + cmake -G "Visual Studio 17 2022"
           (compiling-cloudviewer-windows.md).

Every argv below mirrors the corresponding guide; nothing is invented.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .installer import IS_LINUX, IS_MACOS, IS_WINDOWS

REPO_URL = "https://github.com/Asher-1/ACloudViewer.git"
DEFAULT_SOURCE_DIR = Path.home() / "ACloudViewer-src"
DEFAULT_PREFIX = Path.home() / "install"
ENV_NAME = "cloudViewer"
PYTHON_VERSION = "3.12"


class SourceBuildError(Exception):
    pass


@dataclass
class BuildStep:
    """One shell-out step of a source build plan."""
    name: str
    argv: list[str]
    cwd: Path | None = None
    note: str = ""
    optional: bool = False   # non-zero exit -> warn and continue


@dataclass
class BuildPlan:
    platform: str
    source_dir: Path
    build_dir: Path
    prefix: Path
    steps: list[BuildStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"Platform: {self.platform}",
                 f"Source:   {self.source_dir}",
                 f"Build:    {self.build_dir}",
                 f"Prefix:   {self.prefix}"]
        if self.notes:
            lines.extend(f"Note:     {n}" for n in self.notes)
        lines.append("Steps:")
        for i, step in enumerate(self.steps, 1):
            suffix = "  (optional)" if step.optional else ""
            lines.append(f"  [{i}/{len(self.steps)}] {step.name}{suffix}")
            if step.note:
                lines.append(f"        {step.note}")
        return "\n".join(lines)


def _macos_cmake_flags(prefix: Path) -> list[str]:
    """cmake flags exactly as listed in compiling-cloudviewer-macos.md."""
    return [
        "-DDEVELOPER_BUILD=OFF", "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        "-DBUILD_WITH_CONDA=ON", "-DCONDA_PREFIX=$CONDA_PREFIX",
        "-DCMAKE_PREFIX_PATH=$CONDA_PREFIX",
        "-DBUILD_UNIT_TESTS=ON", "-DBUILD_BENCHMARKS=OFF",
        "-DWITH_OPENMP=ON", "-DWITH_IPP=ON", "-DWITH_SIMD=ON", "-DUSE_SIMD=ON",
        "-DUSE_QT6=OFF", "-DPACKAGE=ON", "-DUSE_VTK_BACKEND=ON",
        "-DBUILD_WEBRTC=OFF", "-DBUILD_OPENCV=ON", "-DUSE_SYSTEM_OPENCV=OFF",
        "-DBUILD_RECONSTRUCTION=ON", "-DBUILD_CUDA_MODULE=OFF",
        "-DBUILD_JUPYTER_EXTENSION=OFF", "-DBUILD_LIBREALSENSE=OFF",
        "-DBUILD_AZURE_KINECT=OFF", "-DBUILD_PYTORCH_OPS=OFF",
        "-DBUILD_TENSORFLOW_OPS=OFF", "-DBUNDLE_CLOUDVIEWER_ML=OFF",
        "-DCVCORELIB_USE_CGAL=ON", "-DCVCORELIB_SHARED=ON",
        "-DCVCORELIB_USE_QT_CONCURRENT=ON",
        "-DOPTION_USE_GDAL=OFF", "-DOPTION_USE_DXF_LIB=ON",
        "-DOPTION_USE_RANSAC_LIB=ON", "-DOPTION_USE_SHAPE_LIB=ON",
        "-DPLUGIN_IO_QDRACO=ON", "-DPLUGIN_IO_QLAS=ON", "-DPLUGIN_IO_QADDITIONAL=ON",
        "-DPLUGIN_IO_QCORE=ON", "-DPLUGIN_IO_QCSV_MATRIX=ON", "-DPLUGIN_IO_QE57=ON",
        "-DPLUGIN_IO_QMESH=ON", "-DPLUGIN_IO_QPDAL=OFF", "-DPLUGIN_IO_QPHOTOSCAN=ON",
        "-DPLUGIN_IO_QRDB=OFF", "-DPLUGIN_IO_QFBX=OFF", "-DPLUGIN_IO_QSTEP=OFF",
        "-DPLUGIN_STANDARD_QCORK=ON", "-DPLUGIN_STANDARD_QJSONRPC=ON",
        "-DPLUGIN_STANDARD_QCLOUDLAYERS=ON",
        "-DPLUGIN_STANDARD_MASONRY_QAUTO_SEG=ON",
        "-DPLUGIN_STANDARD_MASONRY_QMANUAL_SEG=ON",
        "-DPLUGIN_STANDARD_QANIMATION=ON", "-DPLUGIN_STANDARD_QBROOM=ON",
        "-DQANIMATION_WITH_FFMPEG_SUPPORT=ON", "-DPLUGIN_STANDARD_QCANUPO=ON",
        "-DPLUGIN_STANDARD_QCOLORIMETRIC_SEGMENTER=ON", "-DPLUGIN_STANDARD_QCOMPASS=ON",
        "-DPLUGIN_STANDARD_QCSF=ON", "-DPLUGIN_STANDARD_QFACETS=ON",
        "-DPLUGIN_STANDARD_QHOUGH_NORMALS=ON", "-DPLUGIN_STANDARD_QM3C2=ON",
        "-DPLUGIN_STANDARD_QMPLANE=ON", "-DPLUGIN_STANDARD_QPCL=ON",
        "-DPLUGIN_STANDARD_QPCV=ON", "-DPLUGIN_STANDARD_QPOISSON_RECON=ON",
        "-DPLUGIN_STANDARD_QRANSAC_SD=ON", "-DPLUGIN_STANDARD_QSRA=ON",
        "-DPLUGIN_STANDARD_3DMASC=ON", "-DPLUGIN_STANDARD_QTREEISO=ON",
        "-DPLUGIN_STANDARD_QVOXFALL=ON", "-DPLUGIN_STANDARD_G3POINT=ON",
        "-DPLUGIN_STANDARD_QSIBR=OFF", "-DAICore_ENABLED=ON",
        "-DPLUGIN_STANDARD_QDA3=ON", "-DPLUGIN_STANDARD_QDEEPLSD=ON",
        "-DPLUGIN_STANDARD_QFACEDETECT=ON", "-DPLUGIN_STANDARD_QFREESPLATTER=ON",
        "-DPLUGIN_STANDARD_QLIGHTGLUE=ON", "-DPLUGIN_STANDARD_QRFDETR=ON",
        "-DPLUGIN_STANDARD_QRMBG=ON", "-DPLUGIN_STANDARD_QYOLO=ON",
        "-DPLUGIN_STANDARD_QSAM3=ON", "-DPLUGIN_STANDARD_QSAM3D=ON",
        "-DPLUGIN_STANDARD_QTRELLIS=ON", "-DBUILD_SPIRULA=ON",
        "-DPLUGIN_STANDARD_QSPIRULA=ON", "-DPLUGIN_STANDARD_QGKD=ON",
        "-DPLUGIN_STANDARD_QOCR=ON", "-DPLUGIN_STANDARD_QRAM=ON",
        "-DPLUGIN_STANDARD_QRELATEANYTHING=ON", "-DPLUGIN_STANDARD_QLINGBOTMAP=ON",
        "-DPLUGIN_STANDARD_QANYLABELING=ON", "-DPLUGIN_STANDARD_QMAPANYTHING=ON",
        "-DPLUGIN_STANDARD_QOPENPCDET=ON", "-DPLUGIN_STANDARD_QINSTANTMESH=ON",
        "-DPLUGIN_STANDARD_QVLXSEEK=ON", "-DPLUGIN_STANDARD_QQUERYSPLAT=ON",
        "-DPLUGIN_PYTHON=ON", "-DBUILD_PYTHON_MODULE=ON",
    ]


def _windows_cmake_flags(cpu_only: bool) -> list[str]:
    """cmake flags exactly as listed in compiling-cloudviewer-windows.md."""
    cuda = ["-DBUILD_CUDA_MODULE=ON", "-DAICore_USE_CUDA=ON",
            "-DAICore_BUNDLE_CUDA_RUNTIME=ON"] if not cpu_only else \
           ["-DBUILD_CUDA_MODULE=OFF", "-DAICore_USE_CUDA=OFF",
            "-DAICore_BUNDLE_CUDA_RUNTIME=OFF"]
    return [
        "-DDEVELOPER_BUILD=OFF", "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_WITH_CONDA=ON",
        "-DBUILD_UNIT_TESTS=OFF", "-DBUILD_EXAMPLES=OFF", "-DBUILD_BENCHMARKS=OFF",
        "-DBUILD_SHARED_LIBS=OFF", "-DSTATIC_WINDOWS_RUNTIME=OFF",
        "-DWITH_OPENMP=ON", "-DWITH_SIMD=ON", "-DUSE_SIMD=ON", "-DPACKAGE=ON",
        "-DBUILD_OPENCV=ON", "-DBUILD_RECONSTRUCTION=ON", "-DUSE_VTK_BACKEND=ON",
        "-DCVCORELIB_USE_CGAL=ON", "-DCVCORELIB_SHARED=ON",
        "-DCVCORELIB_USE_QT_CONCURRENT=ON",
        "-DOPTION_USE_GDAL=OFF", "-DOPTION_USE_DXF_LIB=ON",
        "-DPLUGIN_IO_QDRACO=ON", "-DPLUGIN_IO_QLAS=ON", "-DPLUGIN_IO_QADDITIONAL=ON",
        "-DPLUGIN_IO_QCORE=ON", "-DPLUGIN_IO_QCSV_MATRIX=ON", "-DPLUGIN_IO_QE57=ON",
        "-DPLUGIN_IO_QMESH=ON", "-DPLUGIN_IO_QPDAL=OFF", "-DPLUGIN_IO_QPHOTOSCAN=ON",
        "-DPLUGIN_IO_QRDB=OFF", "-DPLUGIN_IO_QRDB_FETCH_DEPENDENCY=OFF",
        "-DPLUGIN_IO_QFBX=ON", "-DPLUGIN_IO_QSTEP=OFF",
        "-DPLUGIN_STANDARD_QCORK=ON", "-DPLUGIN_STANDARD_QJSONRPC=ON",
        "-DPLUGIN_STANDARD_QCLOUDLAYERS=ON",
        "-DPLUGIN_STANDARD_MASONRY_QAUTO_SEG=ON",
        "-DPLUGIN_STANDARD_MASONRY_QMANUAL_SEG=ON",
        "-DPLUGIN_STANDARD_QANIMATION=ON", "-DPLUGIN_STANDARD_QBROOM=ON",
        "-DQANIMATION_WITH_FFMPEG_SUPPORT=ON", "-DPLUGIN_STANDARD_QCANUPO=ON",
        "-DPLUGIN_STANDARD_QCOLORIMETRIC_SEGMENTER=ON", "-DPLUGIN_STANDARD_QCOMPASS=ON",
        "-DPLUGIN_STANDARD_QCSF=ON", "-DPLUGIN_STANDARD_QFACETS=ON",
        "-DPLUGIN_STANDARD_QHOUGH_NORMALS=ON", "-DPLUGIN_STANDARD_QM3C2=ON",
        "-DPLUGIN_STANDARD_QMPLANE=ON", "-DPLUGIN_STANDARD_QPCL=ON",
        "-DPLUGIN_STANDARD_QPCV=ON", "-DPLUGIN_STANDARD_QPOISSON_RECON=ON",
        "-DPLUGIN_STANDARD_QSRA=ON", "-DPLUGIN_STANDARD_3DMASC=ON",
        "-DPLUGIN_STANDARD_QTREEISO=ON", "-DPLUGIN_STANDARD_QVOXFALL=ON",
        "-DPLUGIN_STANDARD_G3POINT=ON", "-DPLUGIN_STANDARD_QSIBR=ON",
        "-DAICore_ENABLED=ON", "-DAICore_USE_VULKAN=ON",
        "-DPLUGIN_STANDARD_QDA3=ON", "-DPLUGIN_STANDARD_QDEEPLSD=ON",
        "-DPLUGIN_STANDARD_QFACEDETECT=ON", "-DPLUGIN_STANDARD_QFREESPLATTER=ON",
        "-DPLUGIN_STANDARD_QLIGHTGLUE=ON", "-DPLUGIN_STANDARD_QRFDETR=ON",
        "-DPLUGIN_STANDARD_QRMBG=ON", "-DPLUGIN_STANDARD_QYOLO=ON",
        "-DPLUGIN_STANDARD_QSAM3=ON", "-DPLUGIN_STANDARD_QSAM3D=ON",
        "-DPLUGIN_STANDARD_QTRELLIS=ON", "-DBUILD_SPIRULA=ON",
        "-DPLUGIN_STANDARD_QSPIRULA=ON", "-DPLUGIN_STANDARD_QGKD=ON",
        "-DPLUGIN_STANDARD_QOCR=ON", "-DPLUGIN_STANDARD_QRAM=ON",
        "-DPLUGIN_STANDARD_QRELATEANYTHING=ON", "-DPLUGIN_STANDARD_QLINGBOTMAP=ON",
        "-DPLUGIN_STANDARD_QANYLABELING=ON", "-DPLUGIN_STANDARD_QMAPANYTHING=ON",
        "-DPLUGIN_STANDARD_QOPENPCDET=ON", "-DPLUGIN_STANDARD_QINSTANTMESH=ON",
        "-DPLUGIN_STANDARD_QVLXSEEK=ON", "-DPLUGIN_STANDARD_QQUERYSPLAT=ON",
        "-DPLUGIN_PYTHON=ON", "-DBUILD_PYTHON_MODULE=ON",
    ] + cuda


def _default_jobs() -> int:
    return max(1, min((__import__("os").cpu_count() or 4), 12))


def plan_source_build(
    platform: str | None = None,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    prefix: Path = DEFAULT_PREFIX,
    jobs: int | None = None,
    cpu_only: bool = False,
    skip_env: bool = False,
    skip_build: bool = False,
) -> BuildPlan:
    """Build the step list for one platform. Pure: no side effects."""
    if platform is None:
        platform = "linux" if IS_LINUX else "macos" if IS_MACOS else \
            "windows" if IS_WINDOWS else "unknown"
    if platform not in ("linux", "macos", "windows"):
        raise SourceBuildError(
            f"Unsupported platform for source build: {platform!r} "
            "(linux/macos/windows only)")
    jobs = jobs or _default_jobs()
    source_dir = Path(source_dir)
    build_dir = source_dir / "build_app"
    plan = BuildPlan(platform=platform, source_dir=source_dir,
                     build_dir=build_dir, prefix=Path(prefix))

    if platform == "linux":
        script = source_dir / "docs" / "guides" / "compiling_doc" / \
            "setup_and_build_acloudviewer_linux.sh"
        argv = ["bash", str(script), "--jobs", str(jobs),
                "--prefix", str(prefix), "--source-dir", str(source_dir)]
        if skip_build:
            argv.append("--skip-build")
        plan.steps.append(BuildStep(
            name="setup-and-build (apt deps, pyenv, Vulkan env, VTK+PCL, "
                 "configure, make)",
            argv=argv, cwd=source_dir,
            note="Idempotent one-click script implementing Option A of "
                 "compiling-cloudviewer-linux.md (apt + pyenv; conda is NOT "
                 "used on Linux). Re-runs only missing stages, so --skip-env "
                 "is unnecessary.",
        ))
        return plan

    if platform == "macos":
        yml = source_dir / ".ci" / "conda_macos_cloudViewer.yml"
        env_script = (
            f'YML="{yml}"; TMP="$(mktemp)"; '
            f'sed "s/3.10/{PYTHON_VERSION}/g" "$YML" > "$TMP"; '
            f'if conda env list | grep -qE "^{ENV_NAME}[[:space:]]"; then '
            f'echo "conda env {ENV_NAME} exists - skipping create"; '
            f'else conda env create -f "$TMP"; fi; rm -f "$TMP"'
        )
        if not skip_env:
            plan.steps.append(BuildStep(
                name="conda env (cloudViewer) from .ci/conda_macos_cloudViewer.yml",
                argv=["bash", "-c", env_script],
                note="compiling-cloudviewer-macos.md 'Set Up Python (Conda)'; "
                     "skipped when the env already exists (idempotent).",
            ))
        plan.steps.append(BuildStep(
            name="configure (cmake with BUILD_WITH_CONDA=ON)",
            argv=["conda", "run", "-n", ENV_NAME, "bash", "-c",
                  'export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig:'
                  '$PKG_CONFIG_PATH"; '
                  'export PATH="$CONDA_PREFIX/lib:$CONDA_PREFIX/lib/pkgconfig:'
                  '$CONDA_PREFIX/lib/cmake:$PATH"; '
                  f'cmake -S "{source_dir}" -B "{build_dir}" '
                  + " ".join(_macos_cmake_flags(prefix))],
            note="compiling-cloudviewer-macos.md 'Building the APP'; macOS uses "
                 "Metal for AICore (no Vulkan/CUDA flags).",
        ))
        if not skip_build:
            plan.steps.append(BuildStep(
                name="build (cmake --build, equivalent to make -j)",
                argv=["conda", "run", "-n", ENV_NAME, "bash", "-c",
                      f'cmake --build "{build_dir}" -j {jobs}'],
                cwd=build_dir if build_dir.exists() else None,
            ))
            plan.steps.append(BuildStep(
                name="install (cmake --install, equivalent to make install)",
                argv=["conda", "run", "-n", ENV_NAME, "bash", "-c",
                      f'cmake --install "{build_dir}"'],
            ))
        plan.notes.append("qSIBR is OFF on macOS per the guide/CI default.")
        return plan

    # windows
    src = str(source_dir)
    build = str(build_dir)
    if not skip_env:
        plan.steps.append(BuildStep(
            name="Vulkan SDK build environment (AICore)",
            argv=["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                  "-File", str(source_dir / "util" / "vulkan" /
                               "install_vulkan_sdk_windows.ps1")],
            optional=True,
            note="compiling-cloudviewer-windows.md: run before configure. "
                 "Optional: a failure (e.g. no admin rights) only disables "
                 "Vulkan AICore acceleration.",
        ))
        env_script = (
            f"$yml = '{src}\\.ci\\conda_windows_cloudViewer.yml'; "
            f"$tmp = Join-Path $env:TEMP 'conda_windows_cloudViewer.yml'; "
            f"Copy-Item $yml $tmp -Force; "
            f"(Get-Content $tmp) -replace '3.10', '{PYTHON_VERSION}' | "
            f"Set-Content $tmp; "
            f"if (-not (conda env list | Select-String -Quiet '^{ENV_NAME} ')) "
            f"{{ conda env create -f $tmp }}"
        )
        plan.steps.append(BuildStep(
            name="conda env (cloudViewer) from .ci/conda_windows_cloudViewer.yml",
            argv=["powershell", "-NoProfile", "-Command", env_script],
            note="compiling-cloudviewer-windows.md 'Set Up Python (Conda)'; "
                 "skipped when the env already exists (idempotent).",
        ))
    # setup_conda_env.ps1 exports CONDA_LIB_DIR/EIGEN_ROOT_DIR in-process, so
    # configure must run in the SAME powershell invocation (guide lines 97-107).
    plan.steps.append(BuildStep(
        name="configure (setup_conda_env.ps1 + cmake, one shell)",
        argv=["conda", "run", "-n", ENV_NAME, "powershell", "-NoProfile",
              "-ExecutionPolicy", "Bypass", "-Command",
              f"& '{source_dir / 'scripts' / 'setup_conda_env.ps1'}'; "
              f"cmake -S '{src}' -B '{build}' -G 'Visual Studio 17 2022' "
              f"-A x64 -DCMAKE_INSTALL_PREFIX='{prefix}' "
              + " ".join(_windows_cmake_flags(cpu_only))
              + " -DCONDA_PREFIX=$env:CONDA_PREFIX"
                " -DCMAKE_PREFIX_PATH=$env:CONDA_LIB_DIR"
                " -DEIGEN_ROOT_DIR=$env:EIGEN_ROOT_DIR"],
        note="compiling-cloudviewer-windows.md 'Building the APP'.",
    ))
    if not skip_build:
        plan.steps.append(BuildStep(
            name="build (cmake --build --config Release)",
            argv=["conda", "run", "-n", ENV_NAME, "powershell", "-NoProfile",
                  "-Command", f"cmake --build '{build}' --config Release "
                              f"--parallel {jobs}"],
        ))
        plan.steps.append(BuildStep(
            name="install (cmake --install --config Release)",
            argv=["conda", "run", "-n", ENV_NAME, "powershell", "-NoProfile",
                  "-Command", f"cmake --install '{build}' --config Release"],
        ))
    plan.notes.append("CUDA is ON by default on Windows (guide default); "
                      "pass --cpu-only to disable it.")
    return plan


def run_source_build(
    plan: BuildPlan,
    runner=subprocess.run,
    echo=print,
    dry_run: bool = False,
    timeout: int | None = None,
) -> list[dict]:
    """Execute a plan sequentially; optional steps tolerate failure."""
    results: list[dict] = []
    for i, step in enumerate(plan.steps, 1):
        echo(f"[{i}/{len(plan.steps)}] {step.name}")
        if dry_run:
            echo(f"    (dry-run) would run: {step.argv}")
            results.append({"step": step.name, "action": "dry-run"})
            continue
        if step.cwd is not None and not step.cwd.exists():
            step.cwd.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            completed = runner(step.argv, cwd=step.cwd, timeout=timeout)
            rc = getattr(completed, "returncode", completed if isinstance(
                completed, int) else -1)
        except Exception as e:                      # noqa: BLE001 - report and decide
            rc = -1
            echo(f"    error: {e}")
        duration = round(time.monotonic() - started, 1)
        if rc != 0 and not step.optional:
            raise SourceBuildError(
                f"Step '{step.name}' failed (exit {rc}). Fix the issue and "
                f"re-run; every step is idempotent where the underlying tool "
                f"supports it.")
        if rc != 0:
            echo(f"    optional step failed (exit {rc}) - continuing")
        results.append({"step": step.name, "exit_code": rc,
                        "seconds": duration,
                        "optional": step.optional})
    return results


def verify_build(plan: BuildPlan) -> str | None:
    """Locate the built ACloudViewer binary (build tree first, then prefix)."""
    from .installer import _find_binary_in_dir
    for root in (plan.build_dir, plan.prefix):
        if root.exists():
            binary = _find_binary_in_dir(root)
            if binary:
                return str(binary)
    return None
