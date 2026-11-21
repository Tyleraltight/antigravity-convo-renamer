# AGENTS.md - antigravity-convo-renamer

## Architecture
- `renamer.py`: Core engine (daemon/CLI discovery, loopback-only proxy-free RPC client, bounds-checked protobuf parser, sidebar-width semantic compaction, optional `rules.json` loader, Windows Named Mutex).
- `scripts/`: Windows Task Scheduler installer (`install_task.ps1`, `uninstall_task.ps1`) and portable wrappers (`run_silent.vbs`, `run_cli.bat`).
- `rules.example.json`: Template for user-defined `workspace_rules`, `custom_translations`, and `tech_allowlist`. Never commit personal `rules.json`.
- `tests/test_renamer.py`: Unit test suite (`python -m unittest discover -s tests -v`).

## Conventions
- Keep core defaults generic; never commit local user directories, personal coursework names, or live tokens.
- Any changes to `README.md` or `assets/readme/*.svg` must pass `audit_readme.py`.
