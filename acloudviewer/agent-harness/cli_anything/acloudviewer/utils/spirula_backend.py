"""Spirula Studio backend — locates and drives the standalone GPLv3
`spirula` executable (3D Gaussian Splatting training) shipped with
ACloudViewer (`bin/ACloudViewer/spirula` when built with BUILD_SPIRULA=ON).

Process-boundary contract: zero upstream patches; sync = SPIRULA_TAG bump.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class SpirulaError(Exception):
    """Raised when the spirula executable is missing or a command fails."""


class SpirulaBackend:
    """Wrapper around the spirula CLI binary."""

    def __init__(self, binary: str | None = None):
        self._binary = binary or self.find_binary()
        if not self._binary:
            raise SpirulaError(
                "spirula binary not found. Set SPIRULA_EXE env var or add "
                "spirula to PATH (shipped at <install>/bin/ACloudViewer/"
                "spirula with BUILD_SPIRULA=ON)."
            )

    # ── discovery ─────────────────────────────────────────────────────────

    @staticmethod
    def _binary_names() -> list[str]:
        suffix = ".exe" if platform.system() == "Windows" else ""
        # CUDA variant first: preferred when an NVIDIA driver is present.
        return [f"spirula-cuda{suffix}", f"spirula{suffix}"]

    def find_binary(self) -> str | None:
        explicit = os.environ.get("SPIRULA_EXE")
        if explicit and Path(explicit).exists():
            return explicit

        acv_binary = os.environ.get("ACV_BINARY")
        if acv_binary:
            acv_dir = Path(acv_binary).parent
            for name in self._binary_names():
                candidate = acv_dir / name
                if candidate.exists():
                    return str(candidate)

        for name in self._binary_names():
            found = shutil.which(name)
            if found:
                return found
        return None

    # ── commands ──────────────────────────────────────────────────────────

    def version(self) -> str:
        return self._run_sync(["--version"], timeout=10).get("stdout", "").strip()

    def devices(self, timeout: int = 10) -> list[dict]:
        """Enumerate compute devices. Raises SpirulaError on enumeration
        timeout (a Vulkan-capable GPU/driver is required)."""
        out = self._run_sync(
            ["--device", "auto", "--version"], timeout=timeout
        ).get("stdout", "")
        row_re = re.compile(
            r"\[(-?\d+)\]\s+(\S.*?)\s+\(([^,]+),\s*(\d+)\s*MB\)(.*)")
        devices: list[dict] = []
        for line in out.splitlines():
            m = row_re.search(line)
            if not m:
                continue
            devices.append({
                "index": int(m.group(1)),
                "name": m.group(2).strip(),
                "type": m.group(3).strip(),
                "vram_mb": int(m.group(4)),
                "current": line.strip().startswith("*"),
                "usable": not m.group(5).strip(),
            })
        return devices

    def train(self, dataset: str, output_name: str | None = None,
              device: str = "auto", extra_args: str = "",
              timeout: int = 3600) -> dict:
        """Headless 3DGS training. timeout bounds the whole run — use a large
        value (or drive `spirula train` via subprocess.Popen yourself) for
        production-scale datasets."""
        args = ["train", dataset]
        if output_name:
            args += ["--output-dir-name", output_name]
        if device and device != "auto":
            args += ["--device", device]
        args += extra_args.split()
        result = self._run_sync(args, timeout=timeout)
        run_dir = Path(dataset).resolve().parent / "outputs" / (
            output_name or "outputs")
        result["run_dir_hint"] = str(run_dir)
        return result

    def run(self, subcommand: str, args: list[str],
            timeout: int = 3600) -> dict:
        """Generic passthrough for any headless spirula subcommand
        (sfm/mesh/geometry/e57/lidar/partition/encode/...)."""
        return self._run_sync([subcommand] + list(args), timeout=timeout)

    def progress(self, run_dir: str) -> dict:
        """Structured progress from a spirula run directory (zero-patch
        alternative to parsing upstream log formats)."""
        d = Path(run_dir)
        if not d.exists():
            raise SpirulaError(f"Run directory not found: {run_dir}")
        ckpts = sorted(d.glob("step-*.ckpt"))
        latest = ckpts[-1].name if ckpts else None
        step = (int(latest.split("-")[1].split(".")[0])
                if latest else None)
        splat = d / "splat.ply"
        return {
            "run_dir": str(d),
            "config": (d / "config.json").exists(),
            "total_checkpoints": len(ckpts),
            "latest_checkpoint": latest,
            "latest_step": step,
            "finished": splat.exists(),
            "splat_ply": str(splat) if splat.exists() else None,
        }

    def launch_gui(self) -> int:
        """Start the official Spirula Studio GUI, detached. Returns the pid."""
        return subprocess.Popen(
            [self._binary], cwd=Path(self._binary).parent).pid

    # ── internals ─────────────────────────────────────────────────────────

    def _run_sync(self, args: list[str], timeout: int) -> dict:
        proc = subprocess.run([self._binary] + args,
                              capture_output=True, text=True,
                              timeout=timeout)
        if proc.returncode != 0:
            raise SpirulaError(
                f"spirula {' '.join(args[:2])}... exited with "
                f"{proc.returncode}: {proc.stderr[-500:]}")
        return {"exit_code": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr}
