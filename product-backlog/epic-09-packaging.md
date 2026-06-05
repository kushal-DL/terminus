# Epic 9: Packaging & Distribution

> **Priority**: P0 (config), P2 (distribution)  
> **Status**: ✅ All 9 stories done  
> **Sprint**: 1 (config), 5+ (distribution)

---

## Feature 9.1 — Package Configuration

### Story 9.1.1 — Console Script Entry Point

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `[project.scripts] terminus = "terminus.__main__:main"` in pyproject.toml
- [ ] `python -m terminus` works as alternative
- [ ] Entry point passes CLI args (--host, --port, --public, --server-only, --verbose)

**Note**: Currently `colony = "colony.__main__:main"` — needs update after rename (Epic 1.3)

---

### Story 9.1.2 — Dependency Pins

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] All deps pinned with compatible ranges: `textual>=0.40`, `fastapi>=0.100`, etc.
- [ ] `uv pip install .` resolves without conflicts
- [ ] No unnecessary transitive deps

---

### Story 9.1.3 — Python Version Requirement

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `requires-python = ">=3.11"` set
- [ ] Tested on 3.11, 3.12, 3.13, 3.14

---

### Story 9.1.4 — README

**Status**: ✅ Done (needs rename update)

**Acceptance Criteria**:
- [ ] Overview: what the game is, 2-3 sentences
- [ ] Install: `pip install .` or `pip install git+<url>`
- [ ] Quickstart: create game, join game, basic controls
- [ ] Requirements: Python 3.11+, terminal 80×24+
- [ ] Optional: cloudflared for public multiplayer

---

### Story 9.1.5 — .gitignore

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Standard Python ignores: `__pycache__/`, `*.pyc`, `.egg-info/`, `dist/`, `build/`
- [ ] Venv ignores: `.venv/`, `venv/`
- [ ] IDE: `.vscode/`, `.idea/`
- [ ] Game data: `*.db` (local game saves)

---

## Feature 9.2 — Distribution Options

### Story 9.2.1 — Git Install Documentation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Document in README: `pip install git+https://github.com/<user>/terminus.git`
- [ ] Works without cloning repo
- [ ] Installs all dependencies automatically
- [ ] Console script `terminus` available after install

---

### Story 9.2.2 — PyInstaller Single Executable

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `terminus.spec` PyInstaller spec file
- [ ] Produces single `terminus.exe` (Windows) / `terminus` (Linux/macOS)
- [ ] Includes all data files (JSON, .tcss)
- [ ] Size target: <50MB
- [ ] No Python installation required to run
- [ ] Build command: `pyinstaller terminus.spec`

---

### Story 9.2.3 — GitHub Release Workflow

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] GitHub Actions workflow: `.github/workflows/release.yml`
- [ ] Trigger: push tag `v*.*.*`
- [ ] Steps: test → build wheel → build exe (3 platforms) → create release → upload assets
- [ ] Release includes: wheel, Windows exe, Linux binary, macOS binary
- [ ] Changelog auto-generated from commit messages

---

### Story 9.2.4 — PyPI Publication

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Package name: `terminus-game` (avoid conflicts)
- [ ] `python -m build` produces valid wheel + sdist
- [ ] `twine check dist/*` passes
- [ ] Published to PyPI: `pip install terminus-game`
- [ ] Version managed in `pyproject.toml` (single source of truth)
