# CNC Box Creator — Project Notes

## Git and GitHub sync

This repo is synced to a PRIVATE GitHub repository:
https://github.com/silvermanphoto/CNC-boxcreator

Remote: `origin` (HTTPS). After every commit, push to keep GitHub in sync.

Rules:
1. ALWAYS push after committing — a local-only commit is incomplete work.
   If Joel forgets, remind him.
2. Never force-push (`--force`) without Joel's explicit approval.
3. The repo is PRIVATE. Do not change its visibility.
4. Never commit build artifacts, secrets, or logs. The `.gitignore` covers
   these — if you add a new category of generated or sensitive file, add it
   to `.gitignore` before committing.
5. Do NOT commit files that would push the repo past GitHub's size limits.
   Build outputs, compiled binaries, packaged installers, and bundled
   runtimes are never necessary in the repo — the code should be sufficient
   to rebuild them from scratch. When in doubt, check file sizes before
   committing.
6. Databases (.db, .sqlite, .sqlite3) MUST be committed and pushed — they
   contain Joel's data and GitHub is the backup. If a database file exceeds
   100 MB, warn Joel before committing so we can discuss options (e.g., Git
   LFS).
