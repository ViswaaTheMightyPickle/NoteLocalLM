# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a minimal workspace with no application source tree, test suite, or build configuration. Keep future additions organized by purpose:

- `data/` for raw or cleaned datasets, preferably CSV or other documented tabular formats.
- `src/` for reusable code, scripts, or modules.
- `tests/` for automated tests that mirror `src/` paths.
- `docs/` for notes, data dictionaries, and methodology.

Avoid placing generated outputs at the repository root. If large derived files are needed, put them under `outputs/` and document how to regenerate them.

## Build, Test, and Development Commands

No project-specific commands are defined yet. When adding tooling, prefer commands that can be run from the repository root and document them here. Examples:

- `python -m pytest` runs Python tests if a Python test suite is added.
- `python src/<script>.py` runs a one-off analysis script.
- `make test` or `npm test` may be added if a Makefile or Node project is introduced.

Keep command names stable so contributors and automation can rely on them.

## Coding Style & Naming Conventions

Use clear, descriptive filenames. For code, prefer lowercase module names with underscores, such as `network_metrics.py`. For datasets, include source or date context where useful, such as `data/exam_results_2017_2018.csv`.

Use UTF-8 encoded text files. Keep CSV headers explicit and stable. For Python, use 4-space indentation and format with `black` if Python tooling is introduced. For JavaScript or TypeScript, use the formatter configured by the project once one exists.

## Testing Guidelines

There is no current testing framework. Add tests with any new reusable code or data transformation logic. Test files should be named predictably, such as `tests/test_network_metrics.py`, and should cover parsing, edge cases, and expected output schemas.

For data work, include small fixture files in `tests/fixtures/` rather than depending on full datasets.

## Commit & Pull Request Guidelines

Git history is not available in this checkout, so no repository-specific commit convention can be inferred. Use concise imperative commit messages, for example `Add CSV validation script` or `Document data schema`.

Pull requests should include a short description, the reason for the change, commands run for verification, and any data format changes. Include screenshots only when the change introduces visual output.

## Security & Configuration Tips

Do not commit secrets, credentials, or private datasets. Store local configuration in ignored environment files, and document required variables in `docs/` or an example config file.
