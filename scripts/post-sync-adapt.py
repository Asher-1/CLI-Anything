#!/usr/bin/env python3
"""Post-sync fork adaptation for Asher-1/CLI-Anything."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".sync-config.json"
ACLOUDVIEWER_ENTRY_BACKUP = REPO_ROOT / "scripts/.acloudviewer-registry-entry.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, check=check, text=True, capture_output=True)


def backup_acloudviewer_entry() -> None:
    registry_path = REPO_ROOT / "registry.json"
    if not registry_path.is_file():
        return
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for cli in data.get("clis", []):
        if cli.get("name") == "acloudviewer":
            ACLOUDVIEWER_ENTRY_BACKUP.parent.mkdir(parents=True, exist_ok=True)
            ACLOUDVIEWER_ENTRY_BACKUP.write_text(
                json.dumps(cli, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"Backed up acloudviewer registry entry to {ACLOUDVIEWER_ENTRY_BACKUP}")
            return


def load_acloudviewer_entry() -> dict | None:
    if ACLOUDVIEWER_ENTRY_BACKUP.is_file():
        return json.loads(ACLOUDVIEWER_ENTRY_BACKUP.read_text(encoding="utf-8"))
    registry_path = REPO_ROOT / "registry.json"
    if registry_path.is_file():
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        for cli in data.get("clis", []):
            if cli.get("name") == "acloudviewer":
                return cli
    return None


def merge_registry() -> None:
    cfg = load_config()
    registry_path = REPO_ROOT / "registry.json"
    fork_entry = load_acloudviewer_entry()

    # If registry JSON is invalid (common after conflicted rebases), rebuild from upstream.
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        json.dumps(data)  # validate serializable
    except (json.JSONDecodeError, TypeError, ValueError):
        print("registry.json invalid after sync; rebuilding from upstream/main")
        upstream_raw = subprocess.check_output(
            ["git", "show", "upstream/main:registry.json"], text=True, cwd=REPO_ROOT
        )
        data = json.loads(upstream_raw)

    if fork_entry is None:
        print("WARNING: acloudviewer registry entry not found; skipping merge insert")
    else:
        names = {cli["name"] for cli in data.get("clis", [])}
        if "acloudviewer" not in names:
            data.setdefault("clis", []).append(fork_entry)
            print("Inserted acloudviewer into registry.json")
        else:
            data["clis"] = [
                fork_entry if cli.get("name") == "acloudviewer" else cli
                for cli in data["clis"]
            ]
            print("Updated existing acloudviewer registry entry")

    data.setdefault("meta", {})
    data["meta"]["repo"] = cfg["fork"]["github_url"]
    registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"registry.json now has {len(data['clis'])} CLI entries")


def merge_gitignore() -> None:
    gitignore = REPO_ROOT / ".gitignore"
    if not gitignore.is_file():
        return
    text = gitignore.read_text(encoding="utf-8")
    blocks = [
        "\n# Fork-only: ACloudViewer harness artifacts\n",
        "/acloudviewer/*\n",
        "/acloudviewer/.*\n",
        "!/acloudviewer/\n",
        "!/acloudviewer/agent-harness/\n",
    ]
    if "/acloudviewer/*" not in text:
        text = text.rstrip() + "".join(blocks) + "\n"
        gitignore.write_text(text, encoding="utf-8")
        print("Added acloudviewer rules to .gitignore")


def patch_repl_skin(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if '"acloudviewer"' in text:
        return
    needle = '"zoom":'
    if needle not in text:
        needle = '"shotcut":'
    accent = '    "acloudviewer":  "\\033[38;5;45m",    # bright teal\n'
    if needle in text:
        text = text.replace(needle, accent + needle, 1)
    hex_needle = '"\\033[38;5;35m":  "#00afaf",  # shotcut teal'
    hex_line = '    "\\033[38;5;45m":  "#00d7ff",  # acloudviewer bright teal\n'
    if hex_needle in text and hex_line.strip() not in text:
        text = text.replace(hex_needle, hex_line + hex_needle, 1)
    path.write_text(text, encoding="utf-8")
    print(f"Patched acloudviewer accent in {path.relative_to(REPO_ROOT)}")


def patch_repl_skins() -> None:
    patch_repl_skin(REPO_ROOT / "cli-anything-plugin" / "repl_skin.py")
    patch_repl_skin(
        REPO_ROOT / "acloudviewer/agent-harness/cli_anything/acloudviewer/utils/repl_skin.py"
    )


def patch_deploy_pages_workflow() -> None:
    path = REPO_ROOT / ".github/workflows/deploy-pages.yml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    marker = "      - name: Generate meta-skill\n        run: python3 .github/scripts/generate_meta_skill.py\n"
    fallback = """
      - name: Publish agent catalog to GitHub Pages (fork fallback)
        run: cp cli-hub-skill/SKILL.md docs/hub/SKILL.txt

"""
    if "Publish agent catalog to GitHub Pages (fork fallback)" not in text:
        if marker in text:
            text = text.replace(marker, marker + fallback, 1)
        else:
            text += fallback

    # Remove upstream-only DO Spaces upload block if present.
    text = re.sub(
        r"\n      - name: Install AWS CLI\n.*?--content-type text/markdown\n",
        "\n",
        text,
        flags=re.DOTALL,
    )
    path.write_text(text, encoding="utf-8")
    print("Patched deploy-pages.yml for fork GitHub Pages skill catalog")


def disable_upstream_publish_workflow() -> None:
    path = REPO_ROOT / ".github/workflows/publish-cli-hub.yml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if re.search(r"^\s+if: false\s+# Disabled on fork", text, re.MULTILINE):
        print("publish-cli-hub.yml already disabled on fork")
        return
    text = text.replace(
        "jobs:\n  publish:",
        "jobs:\n  publish:\n    if: false  # Disabled on fork — avoid publishing to upstream PyPI",
        1,
    )
    path.write_text(text, encoding="utf-8")
    print("Disabled publish-cli-hub.yml on fork")


def patch_cli_hub_registry_urls() -> None:
    path = REPO_ROOT / "cli-hub/cli_hub/registry.py"
    if not path.is_file():
        return
    cfg = load_config()
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/registry.json"',
        f'REGISTRY_URL = "{cfg["fork"]["pages_base"]}/registry.json"',
    )
    text = text.replace(
        'PUBLIC_REGISTRY_URL = "https://hkuds.github.io/CLI-Anything/public_registry.json"',
        f'PUBLIC_REGISTRY_URL = "{cfg["fork"]["pages_base"]}/public_registry.json"',
    )
    path.write_text(text, encoding="utf-8")
    print("Patched cli-hub registry URLs")


def sync_root_skills() -> None:
    script = REPO_ROOT / ".github/scripts/sync_root_skills.py"
    if not script.is_file():
        print("sync_root_skills.py not found; skipping")
        return
    run([sys.executable, str(script)])
    print("Synced repo-root skills/ mirror")


def validate_root_skills() -> None:
    script = REPO_ROOT / ".github/scripts/validate_root_skills.py"
    if not script.is_file():
        print("validate_root_skills.py not found; skipping")
        return
    proc = run([sys.executable, str(script)], check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout or "validate_root_skills failed")
    print("Root skills validation passed")


def remove_openclaw_skill_dir() -> None:
    path = REPO_ROOT / "openclaw-skill"
    if path.is_dir():
        shutil.rmtree(path)
        print("Removed deprecated openclaw-skill/ directory")


def run_customize() -> None:
    cfg = load_config()
    exclude_prefixes = (
        "SYNC_UPSTREAM.md",
        "SYNC_README.md",
        "scripts/sync-upstream-adapt.sh",
        "scripts/post-sync-adapt.py",
        "scripts/resolve-rebase-conflicts.sh",
        "scripts/verify-fork-isolation.sh",
        ".sync-config.json",
    )
    files = run(["git", "ls-files"], check=True).stdout.splitlines()
    changed = 0
    for rel in files:
        if rel.startswith(exclude_prefixes):
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        original = text
        for rep in cfg.get("replacements", []):
            text = text.replace(rep["from"], rep["to"])
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
    print(f"Applied fork URL replacements to {changed} tracked files")


def generate_meta_skill() -> None:
    script = REPO_ROOT / ".github/scripts/generate_meta_skill.py"
    if script.is_file():
        run([sys.executable, str(script)])
        print("Regenerated cli-hub-skill/SKILL.md")


def update_registry_dates() -> None:
    script = REPO_ROOT / ".github/scripts/update_registry_dates.py"
    if script.is_file():
        run([sys.executable, str(script)])
        print("Updated registry dates")


def ensure_hub_registry_copies() -> None:
    hub = REPO_ROOT / "docs/hub"
    hub.mkdir(parents=True, exist_ok=True)
    for name in ("registry.json", "public_registry.json", "matrix_registry.json"):
        src = REPO_ROOT / name
        if src.is_file():
            shutil.copy2(src, hub / name)
            print(f"Copied {name} -> docs/hub/{name}")


def main() -> int:
    backup_acloudviewer_entry()
    merge_registry()
    merge_gitignore()
    patch_repl_skins()
    patch_deploy_pages_workflow()
    disable_upstream_publish_workflow()
    patch_cli_hub_registry_urls()
    remove_openclaw_skill_dir()
    run_customize()
    generate_meta_skill()
    update_registry_dates()
    ensure_hub_registry_copies()
    sync_root_skills()
    validate_root_skills()
    print("Post-sync adaptation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
