#!/usr/bin/env python3
"""Resolve the package to publish for the generic publish.yml workflow.

This repo carries one setup.py package per agent-harness (69 as of
cli-anything-acloudviewer 3.2.0) plus cli-hub at the repo root. One generic
workflow routes them all: the tag prefix (or the workflow_dispatch input)
names the package directory, and the located setup.py owns the PyPI name and
version facts.

Tag mode (default): --ref is "<package>-v<version>"; the version part is
cross-checked against the located setup.py so a stale tag fails the run
before any upload.

Dispatch mode: --package names the directory; no tag guard (the caller
decides what to release).

Output: GitHub Actions output lines (pkgdir, name, version), appended to
--output when it is not "-". Exits 1 with a ::error:: annotation when the
package or version cannot be resolved, before any build step.
"""
import argparse
import os
import pathlib
import re
import sys

_SETUP_CANDIDATES = ("agent-harness/setup.py", "setup.py")


def _setup_field(text: str, field: str) -> str | None:
    """Read a setup() field that is a literal or a module constant.

    Three of the 69 setup.py packages (joplin, mubu, zotero) pass
    ``name=PACKAGE_NAME`` instead of a string literal; resolve the
    identifier from its assignment in the same file before giving up.
    """
    direct = re.search(rf'\b{field}\s*=\s*["\']([^"\']+)["\']', text)
    if direct:
        return direct.group(1)
    indirect = re.search(rf'\b{field}\s*=\s*([A-Za-z_]\w*)\s*[,)]', text)
    if indirect:
        defined = re.search(rf"^{indirect.group(1)}\s*=\s*['\"]([^'\"]+)['\"]",
                            text, re.MULTILINE)
        if defined:
            return defined.group(1)
    return None


def fail(message: str) -> int:
    print(f"::error::{message}", file=sys.stderr)
    return 1


def _setup_for_pkg(pkg: str) -> pathlib.Path | None:
    return next((pathlib.Path(pkg) / part for part in _SETUP_CANDIDATES
                 if (pathlib.Path(pkg) / part).is_file()), None)


def _find_by_pypi_name(prefix: str) -> pathlib.Path | None:
    """Map a PyPI distribution name (e.g. cli-anything-acloudviewer) back to
    its package directory: a tag may carry either the directory name or the
    PyPI name as its prefix. Directory-to-name facts stay owned by each
    setup.py, so new packages need no resolver maintenance."""
    candidates = sorted(pathlib.Path(".").glob("*/agent-harness/setup.py")) + \
        sorted(pathlib.Path(".").glob("*/setup.py"))
    for setup in candidates:
        try:
            text = setup.read_text(encoding="utf-8")
        except OSError:
            continue
        if _setup_field(text, "name") == prefix:
            return setup
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="",
                        help="package directory name (workflow_dispatch mode)")
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME", ""),
                        help="tag ref name (tag mode: <package>-v<version>)")
    parser.add_argument("--output", default="-",
                        help="append key=value lines here; '-' prints to stdout")
    args = parser.parse_args()

    pkg = args.package.strip()
    tag_version = None
    if not pkg:
        # rpartition anchors on the LAST "-v" so package names containing
        # "-v" (none today) still resolve; the version itself has no "-v".
        pkg, _, tag_version = args.ref.rpartition("-v")
        if not pkg or not tag_version:
            return fail(f"tag {args.ref!r} must be named <package>-v<version>")
    setup = _setup_for_pkg(pkg)
    if setup is None and tag_version is not None:
        # Tag prefixes may use the PyPI distribution name instead of the
        # package directory name (e.g. cli-anything-acloudviewer-v3.9.5).
        setup = _find_by_pypi_name(pkg)
    if setup is None:
        return fail(f"no setup.py under {pkg}/agent-harness/ or {pkg}/")
    text = setup.read_text(encoding="utf-8")
    name = _setup_field(text, "name")
    version = _setup_field(text, "version")
    if not (name and version):
        return fail(f"cannot read name/version from {setup}")
    if tag_version is not None and tag_version != version:
        return fail(f"tag {args.ref} does not match {setup} version {version}")

    lines = [f"pkgdir={setup.parent.as_posix()}",
             f"name={name}",
             f"version={version}"]
    if args.output == "-":
        print("\n".join(lines))
    else:
        with open(args.output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
