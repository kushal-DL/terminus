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
- [ ] `python -m pip install -e .` resolves without conflicts
- [ ] No unnecessary transitive deps

---

### Story 9.1.3 — Python Version Requirement

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `requires-python = ">=3.11"` set
- [ ] Tested on 3.11, 3.12, 3.13, 3.14

---

### Story 9.1.4 — README

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Overview: what the game is, 2-3 sentences
- [ ] Install: clone repo + double-click `play.bat` (Windows) or `bash play.sh` (Mac/Linux)
- [ ] Quickstart: create game, join game, basic controls
- [ ] Requirements: Python 3.11+, terminal 120×30+
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

### Story 9.2.1 — Launcher Scripts

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `play.bat` — Windows double-click launcher (creates venv, installs deps, launches game)
- [ ] `play.sh` — Mac/Linux equivalent with version check
- [ ] Both handle first-run setup automatically
- [ ] Subsequent launches are instant (venv already exists)

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

**Status**: ✅ Done (deferred as primary install method — launcher scripts are now preferred)

**Notes**: Package is published as `terminus-game` but PyPI is no longer the primary install method. Users should clone the repo and use `play.bat` / `play.sh`.
