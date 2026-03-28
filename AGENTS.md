# Repository Guidelines

## Project Structure & Module Organization

This repository has two active codepaths:

- `src/eas_client/`: Python EAS core. Key modules are `wbxml/` for decoding, `eas/` for protocol builders/parsers, `ews/` for probes, `transport.py`, `config.py`, and `cli.py`.
- `desktop/`: Tauri desktop shell. `src/` contains the TypeScript UI, and `src-tauri/src/` contains Rust bridge, storage, and session logic.
- `tests/`: Python test suite split by concern (`tests/wbxml`, `tests/eas`, `tests/ews`).
- `desktop/src-tauri/tests/`: Rust-side tests for persistence and account resolution.
- `docs/superpowers/`: design specs and implementation plans.
- `tmp/`: local protocol captures and scratch artifacts; do not treat as stable source.

## Build, Test, and Development Commands

- `PYTHONPATH=src pytest -q`: run the full Python suite.
- `python -m eas_client.cli folders --json`: smoke-test the CLI bridge format.
- `cd desktop && npm run build`: build the desktop frontend bundle.
- `cd desktop && npm run tauri dev`: run the desktop app in development mode.
- `cd desktop/src-tauri && cargo check`: verify the Rust bridge compiles.
- `cd desktop/src-tauri && cargo test --test storage`: run Rust persistence tests.

## Coding Style & Naming Conventions

- Python: 4-space indentation, type hints where already used, keep modules focused by protocol layer.
- TypeScript/Rust: prefer explicit data models over ad hoc maps; keep bridge payloads serializable.
- Use `snake_case` in Python/Rust, `camelCase` in TypeScript, and keep CLI command names hyphenated, such as `message-detail`.
- Prefer small, testable functions over large UI or bridge handlers.

## Testing Guidelines

- Python tests use `pytest`; add focused regression tests next to the affected area.
- Rust tests should live in `desktop/src-tauri/tests/` and cover storage/session behavior.
- Name tests after observable behavior, for example `test_load_account_restores_password_from_secret_store`.
- Run the smallest failing test first, then rerun the broader suite before closing work.

## Commit & Pull Request Guidelines

This workspace currently has no git history, so there is no established commit convention to inherit. Use short imperative commits such as `Fix folder selection crash` or `Add mailbox cache recovery`. For PRs, include:

- a concise summary of the behavior change
- verification commands and results
- screenshots or screen recordings for desktop UI changes
- any protocol or environment assumptions

## Security & Configuration Tips

- Never commit real mailbox credentials.
- Passwords belong in the system keychain, not `account.json`.
- Treat `tmp/*.wbxml` and live server responses as sensitive diagnostic data.
