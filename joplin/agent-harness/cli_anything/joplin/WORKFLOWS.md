# Joplin Workflow Inventory

This document enumerates the workflows that the `cli-anything-joplin` harness
has implemented and verified. It is intended as the single source of truth for
"what does this harness already cover?".

## 1. Categories

The harness covers 12 workflow categories:

1. CLI surface â€?`--help`, every group's help, JSON envelope
2. Project lifecycle â€?`new`, `open`, `info`, `json`, `save`, `status`,
   `session status/undo/redo/history`
3. Notebook lifecycle â€?`list`, `create`, `use`, `remove`
4. Note lifecycle â€?`list`, `create`, `set`, `get`, `remove`
5. Note organization â€?`copy`, `move`, `rename`
6. To-do lifecycle â€?`create`, `list`, `toggle`, `clear`, `done`, `undone`
7. Tag management â€?`list`, `add`, `remove`, `notetags`, `tagnotes`
8. Search â€?`run` (best-effort; some Joplin CLI builds gate this behind GUI mode)
9. Sync â€?`run` (verified with the default no-target configuration)
10. Import / export â€?`import` (md, jex, enex, raw, html, â€?, `export`
   (jex, md, raw, md_frontmatter)
11. Attachments and status â€?`attach add`, `status show`, `status restore`
12. Backend utilities â€?`version`, `dump`, `keymap`, `geoloc`,
    `export-sync-status`, `server`, and `e2ee`

## 2. Workflow points (real-backend)

The real-backend `TestBackendWorkflows` class executes the following short
scripts end-to-end:

- **Note lifecycle** â€?create notebook â†?use â†?create note â†?rename via `set`
  â†?get â†?remove note â†?remove notebook
- **Note organization** â€?create source/target notebooks â†?create note â†?copy
  to target â†?rename source â†?move renamed to target â†?list target â†?cleanup
- **Todo lifecycle** â€?create todo â†?list â†?done â†?undone â†?toggle â†?clear â†?
  cleanup
- **Tagging** â€?create notebook/note â†?add tag â†?list tags â†?notetags â†?
  tagnotes â†?remove tag â†?cleanup
- **Search** â€?create notebook/note â†?search (tolerates GUI-mode rejection)
  â†?cleanup
- **Sync** â€?`sync run` returns a payload even when no target is configured
- **Export** â€?JEX and Markdown for the same note set
- **Import** â€?Markdown directory import into a fresh notebook
- **Attach** â€?create notebook/note â†?attach a real text file â†?verbose get â†?
  cleanup
- **Unicode** â€?`notebooks create/use/notes create/remove` with CJK + Greek
  characters (skipped on Windows due to `cmd.exe` codepage truncation)
- **Session history persists** â€?three mutating commands â†?reload the saved
  project â†?assert every action is present in `history`

## 3. Full end-to-end integration

`TestBackendIntegration.test_full_backend_roundtrip` runs the following phases
in one process against a real Joplin profile, then verifies that the saved
project history contains every expected action:

1. Inspect project (status / info / session)
2. Notebook setup (list, create main, create archive, use main)
3. Note lifecycle (list, create, rename, get, copy to archive, create+move,
   rename via `ren`)
4. Todos (create, list, done, undone, toggle, clear)
5. Tags (add primary, add secondary, list, notetags, tagnotes, remove)
6. Attach (attach real file, verbose get)
7. Status and config (`status show`, `config get sync.target`, `config list`)
8. Sync (no-target no-op)
9. Export (JEX + MD)
10. Cleanup (remove note, remove notebooks, save, final status, session history)

Expected history actions verified after save:

```
notebook.create, notebook.use, note.create, note.set, note.copy, note.move,
note.rename, todo.create, todo.toggle, todo.done, todo.undone, todo.clear,
tag.add, tag.remove, attach.add, interop.export, note.remove, notebook.remove
```

## 4. Test layering summary

| Layer                    | File / class                         | Backend needed | Workflows                       |
|--------------------------|--------------------------------------|----------------|---------------------------------|
| Unit + CLI contract      | `test_core.py`                       | No             | 91 tests |
| CLI subprocess           | `TestCLISubprocess`                  | No             | 10 tests                        |
| Real-backend commands    | `TestBackendCommands`                | Yes            | 6 tests                         |
| Real-backend workflows   | `TestBackendWorkflows`               | Yes            | 11 tests (1 skipped on Windows) |
| End-to-end integration   | `TestBackendIntegration`             | Yes            | 1 test                          |

## 5. Adding a new workflow

1. Add a thin core module under `cli_anything/joplin/core/`.
2. Wire it into `joplin_cli.py` with a single Click command that:
   - records `add_history(...)` on success
   - calls either `sess.snapshot(reason)` (creates an undo point) or
     `sess.mark_dirty()` (just marks dirty) so the auto-save fires.
3. Add a unit test in `test_core.py` (argument shape + JSON envelope).
4. Add a real-backend workflow test in `test_full_e2e.py` under
   `TestBackendWorkflows`.
5. If the workflow is large or demoable, extend
   `TestBackendIntegration.test_full_backend_roundtrip`.

## 6. Implementation guarantees

- Subprocess `stdout`/`stderr` in backend results are verbatim Joplin output.
  Benign Node deprecation warnings are filtered only when deciding whether a
  non-zero exit code is a real failure; they are not stripped from the returned
  streams (so multi-line note bodies and exports stay intact).
- JSON error envelopes use the same `command` identifier as success responses
  (`config.import_file`, `backend.export_sync_status`, `e2ee.decrypt_file`, ?.

## 7. Known limitations

- `joplin search` is gated behind GUI mode on some Joplin CLI 3.x builds. The
  search workflow accepts a clean `ok=false` JSON envelope with the original
  error message.
- Non-ASCII process arguments on Windows pass through `joplin.cmd` â†?`cmd.exe`,
  which downgrades them to the active code page. The harness's JSON state
  itself handles unicode correctly (see the unicode roundtrip in
  `test_core.py`); only the argv path is affected. The unicode workflow test
  is therefore skipped on Windows.
- `joplin version` can fail in npm global layouts because the upstream command
  looks for `../package.json`. `backend version` falls back to the installed
  Joplin `package.json` across every common layout: the symlink-resolved
  binary directory (Unix npm global, Homebrew, nvm), the Windows-style
  sibling `node_modules/joplin`, the Unix-style parent `lib/node_modules/joplin`,
  and `npm root -g` as a last resort.
- `notes remove --permanent` / `notebooks remove --permanent` require Joplin
  terminal CLI >= 3.0. Because Joplin silently ignores unknown options, the
  harness probes `joplin help rmnote` / `rmbook` once per binary and raises
  a clear error on older builds rather than downgrading a permanent delete
  to a trash move. The flag is forwarded as long-form (`--permanent`,
  `--force`); the short `-p` is intentionally avoided since Joplin uses
  `-p` for `--parent` in `mkbook` and `--permanent` only became available
  in 3.x.
