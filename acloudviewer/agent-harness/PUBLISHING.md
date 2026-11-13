# Publishing cli-anything-acloudviewer

## Why it used to be manual

Until v3.2.0 this package had no publish path of its own: the repo's single
PyPI workflow (`publish-cli-hub.yml`) was scoped to cli-hub-py, so every
acloudviewer release was a local `python -m build` + `twine upload` run by
hand. That workflow has since been generalized in place — same file name,
because the file name is the workflow name bound in PyPI Trusted Publishers.

## Fully automated release (v3.2.0 and later)

`.github/workflows/publish-cli-hub.yml` is the single release path for the
whole repo (one setup.py package per agent-harness — 69 in total — plus
cli-hub). It has run in production for cli-hub-py (3 success / 3 skipped
runs, including the cli-hub-py 0.5.0 upload on 2026-08-20). Three ways to
release acloudviewer:

```bash
# Preferred: explicit, tag-guarded (tag must match setup.py)
git tag acloudviewer-v3.2.0
git push origin acloudviewer-v3.2.0
```

A push to main also releases automatically: every package in the workflow's
PACKAGES list is checked against PyPI, and any version missing there is
built and uploaded — advancing a version in `setup.py` and pushing IS the
release action. Every path verifies the version facts, builds the
sdist/wheel, runs `twine check`, and uploads via PyPI **Trusted Publishing**
(OIDC, no tokens stored in GitHub).

### Why only some packages are enabled

The repo ships 69 setup.py packages (`cli-anything-blender`,
`cli-anything-gimp`, ...), but only the ones listed in the workflow's
`PACKAGES` env (currently `acloudviewer cli-hub`) are checked and published:
each package needs a one-time manual Trusted-Publisher binding on pypi.org,
and PyPI rejects uploads for unbound projects — enabling an unreleased
package blindly would fail the run. Enabling one is two steps: add the
package directory to `PACKAGES`, then bind its publisher once (the resolver
at `.github/scripts/resolve_publish_package.py` locates any package by tag
prefix, dispatch input, or `cli-hub`-style root layout).

### First-time one-off setup (PyPI platform requirement, cannot be automated)

1. Register at https://pypi.org and enable 2FA.
2. Bind the **pending publisher** on the account page
   https://pypi.org/manage/account/publishing/ (the project does not exist
   yet, so it has no project page):
   - PyPI project name `cli-anything-acloudviewer`
   - Owner `Asher-1`, repository `CLI-Anything`
   - Workflow `publish-cli-hub.yml`, environment `pypi`
   The first tag push then creates the project and uploads in one go.
3. In GitHub, Settings → Environments → create `pypi` (no secrets needed for
   Trusted Publishing).

From then on, every release is exactly two shell commands (tag + push); the
upload happens on GitHub's CI and cannot be forgotten.

### Token fallback (if Trusted Publishing is unavailable)

1. pypi.org → Account → API tokens → add token scoped to
   `cli-anything-acloudviewer`.
2. GitHub repo → Settings → Environments → `pypi` → add secret
   `PYPI_API_TOKEN`.
3. Replace the publish step in the workflow with:

```yaml
      - name: Publish to PyPI
        working-directory: acloudviewer/agent-harness
        run: twine upload --non-interactive -u __token__ -p "$PYPI_API_TOKEN" dist/*
        env:
          PYPI_API_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
```

## Manual local release (fallback / first creation)

```bash
cd acloudviewer/agent-harness
python -m pip install build twine
python -m build                     # sdist + wheel into dist/
twine check dist/*
twine upload dist/*                 # paste the pypi-... API token at the prompt
```

Never pass the token as a shell argument in a shared shell; use the prompt
or `--config-file` with a protected file.

## Release checklist (all must show the same version)

| Artifact | Location |
|----------|----------|
| Package version | `acloudviewer/agent-harness/setup.py` |
| Registry entry | `registry.json` → `acloudviewer.version` |
| OpenClaw manifest (canonical) | `acloudviewer/agent-harness/cli_anything/acloudviewer/openclaw-skill.json` |
| OpenClaw manifest (mirror) | ACloudViewer repo `agent-integration/openclaw/openclaw-skill.json` |
| Hub skill | `skills/cli-anything-acloudviewer/SKILL.md` (must stay byte-identical to `cli_anything/acloudviewer/skills/SKILL.md`) |
| Git tag | `acloudviewer-v<version>` |

After publishing, verify on https://pypi.org/project/cli-anything-acloudviewer/
and with `pip install -U cli-anything-acloudviewer` in a clean venv.
