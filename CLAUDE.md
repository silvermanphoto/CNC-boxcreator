# CNC Box Creator — Project Notes

> Open findings from the 2026-09 code review: ~/.claude/overseer/reviews/2026-09/CNC-boxcreator.md. Mention them to Joel at the start of each session; delete this line once none are open.

## Working on the generator
- Live code: `CNC Plans/cnc_generator.py` (window and geometry), `blender_generator.py` and `utils.py`. The January `CNC GENERATOR - CARBIDE-OPTIMIZED v1.2x.py` monoliths are archived in `CNC Plans/ARCHIVED PYTHON CODE/`; do not edit them.
- Run: `cd "CNC Plans" && ../venv/bin/python3 cnc_generator.py`. Verify: `../venv/bin/python3 test_gen.py` must print ALL ACCEPTANCE TESTS PASSED (it builds in memory and writes nothing).
- Version: `APP_VERSION` and the two header lines of `cnc_generator.py` move together, one step per commit that changes output or the window.
- Output: each run writes `Box SVGs vN/` into the output folder chosen in the window, which must already exist; `cnc_generator_settings.json` is rewritten on every run and stays out of git. Geometry is nominal: Carbide Create applies the bit offsets, and each master-layout path's data-name is its toolpath type.
- Done means test_gen passes, the success dialog reports the layout check passed, and the master opens in Carbide Create with one outline per part.
- The review and fix reports in the project root are public along with the repo.

## Git and GitHub sync

This repo is synced to a PUBLIC GitHub repository (made public 2026-07-12):
https://github.com/silvermanphoto/CNC-boxcreator

Rules:
1. Never force-push (`--force`) without Joel's explicit approval.
2. The repo is PUBLIC — anyone on the internet can read every file and all history.
   Never commit anything sensitive or personal. Only Joel changes visibility.
3. Never commit build artifacts, secrets, or logs. The `.gitignore` covers
   these — if you add a new category of generated or sensitive file, add it
   to `.gitignore` before committing.
4. Do NOT commit files that would push the repo past GitHub's size limits.
   Build outputs, compiled binaries, packaged installers, and bundled
   runtimes are never necessary in the repo — the code should be sufficient
   to rebuild them from scratch. When in doubt, check file sizes before
   committing.
5. Rule 2 overrides the global rule that databases are committed: never
   commit a database (.db, .sqlite, .sqlite3) to this public repo; ask Joel
   where it should be backed up instead.
