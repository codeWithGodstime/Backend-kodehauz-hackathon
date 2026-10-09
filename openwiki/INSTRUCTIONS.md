# Documentation Structure & Guidelines

## Introduction

This repository is a starter FastAPI application that wires together the public `msflib` packages for authentication, account management, workspace features, and shared settings. The documentation needs to explain how to install the template, configure the required environment variables, and integrate the generated API with the hosted `msflib` modules.

## Documentation requirements

The template does not contain a local `modules/` package tree. Instead, the public API comes from the `msflib` packages pulled in via `pyproject.toml`:

- `msflib` core library
- `msflib-auth`
- `msflib-account`
- `msflib-workspaces`

The OpenWiki docs should therefore document the integration surface of this template and the public services exposed by those packages.

The `openwiki/docs/` folder should follow this structure:

1. `openwiki/docs/index.md` as a landing page with overview, quickstart, and integration guidance.
2. `openwiki/docs/core.md` describing the shared settings and database/bootstrap layer.
3. `openwiki/docs/auth.md` documenting the auth router, dependencies, and JWT flow.
4. `openwiki/docs/account.md` covering accounts, profiles, and account actions.
5. `openwiki/docs/workspaces.md` covering workspaces, users, and workspace orchestration.
6. `openwiki/docs/SUMMARY.md` for the MkDocs navigation.

## Goals for third-party consumption

The docs should provide everything needed for a developer or integrator to stand up the template without browsing the source tree:

- Installation and virtualenv setup with Python 3.10+
- Local database, Redis, and secret configuration
- Quick library tour of the starter app and the public `msflib` components it uses
- Authentication and configuration guidance
- Per-module reference pages with runnable Python examples
- Reproducible local setup and test commands

## Required page structure

Each module doc should include:

- Title and purpose
- Installation / requirements
- Public API table
- Examples & use cases
- Code snippets
- Config & env
- Errors & troubleshooting
- See also links

Add a short YAML frontmatter block if metadata is needed; otherwise keep a consistent heading structure.

## Contribution checklist

- If the public API changes, update the matching docs page.
- Add runnable examples for success and failure cases.
- Update `openwiki/docs/SUMMARY.md` when adding or renaming pages.
- Keep the examples aligned with the actual template code in `app/`.
- Verify the docs build locally with `mkdocs build`.

---
