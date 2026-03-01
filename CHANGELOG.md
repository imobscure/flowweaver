# Changelog

All notable changes to **FlowWeaver** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.2] — 2026-03-01

### Highlights

- **Resiliency at scale** — Corrupted JSON state files are now handled gracefully
  instead of crashing the workflow. The persistence layer logs a warning and
  continues with an empty state, allowing the pipeline to self-heal.
- **Chain-based visualization** — The Mermaid.js viewer now supports DAGs with
  5 000+ tasks thanks to raised `maxTextSize` (1 000 000) and `maxNodes`
  (20 000) limits. The container is responsive up to 1 600 px for comfortable
  viewing on wide monitors.

### Added

- `maxTextSize`, `maxNodes`, and `securityLevel: "loose"` in the Mermaid
  initialisation config (`view_mermaid`) to eliminate the "Maximum text size
  in diagram exceeded" error on high-scale DAGs.
- Responsive `max-width: 1600px` with horizontal scroll for the HTML viewer
  container.
- CI test matrix (`.github/workflows/tests.yml`) running `pytest` on Python
  3.9 – 3.12 for every push and pull request to `main`.
- This `CHANGELOG.md`.

### Changed

- `JSONStateStore._read_store` now catches `ValueError` and
  `UnicodeDecodeError` in addition to `json.JSONDecodeError`, and validates
  that the root element is a `dict` before returning.
- Upgraded all documentation headers, install snippets, and version badges
  from mixed `0.1.2 / 0.3.2` references to a consistent **0.2.2**.
- `view_mermaid` docstring updated to document the new high-scale Mermaid
  configuration.

### Fixed

- Missing `import gc` and `import logging` / `logger` initialisation in
  `src/flowweaver/storage.py` — previously caused `NameError` at runtime
  when `_read_store` logged warnings or when `SQLiteStateStore` invoked
  `gc.collect()`.

---

## [0.2.0] — 2026-02-28

### Added

- **Mermaid.js DAG visualisation** — `export_mermaid`, `save_mermaid`, and
  `view_mermaid` utilities in `flowweaver.utils`.
- Interactive browser-based workflow diagrams with colour-coded task statuses
  (green / red / orange / grey).
- Seven example scripts including `visualize_dag.py`.
- `py.typed` PEP 561 marker for downstream type-checking support.
- MIT `LICENSE` file.

### Fixed

- `Task.execute_async()` called non-existent `self._accepts_context()` —
  replaced with `self._build_injected_args(context)`.
- `verify_system.py` persistence check expected a nested JSON structure that
  didn't match `JSONStateStore`'s flat format.

---

## [0.1.0] — 2026-02-01

### Added

- Core `Task` and `Workflow` classes with DAG validation (cycle detection via DFS).
- `SequentialExecutor`, `ThreadedExecutor`, and `AsyncExecutor`.
- `JSONStateStore` and `SQLiteStateStore` for workflow resumability.
- XCom-style context injection (data-flow between dependent tasks).
- `@task` decorator that preserves function callability for unit testing.
- Topological sort execution plans (Kahn's algorithm).
- Retry logic, timeouts, and status callbacks.

---

[0.2.2]: https://github.com/imobscure/flowweaver/compare/v0.2.0...v0.2.2
[0.2.0]: https://github.com/imobscure/flowweaver/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/imobscure/flowweaver/releases/tag/v0.1.0
