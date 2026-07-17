# runlite: cannot find npx on Windows (command not found)

**RESOLVED 2026-07-17 (runlite v0.1.1).** argv[0] now resolves through
`shutil.which` (PATHEXT-aware) on Windows before spawning, so `.cmd`/`.bat`
shims launch; verified live with `runlite -- npx --version`.

**STATUS at filing: open.**

- **What broke:** `runlite -- npx tsc --noEmit` exits 127 with
  "runlite: command not found: npx", run from Git Bash in a project where
  `npx` works fine in both PowerShell and Git Bash directly.
- **Session:** 2026-07-17, bible-atlas. Wanted a wrapped typecheck.
- **Likely cause:** runlite resolves the child command without honoring
  Windows shims/extensions (`npx.cmd` / `npx.ps1` in the npm prefix dir) —
  probably an exec that only tries the bare name / `.exe`.
- **Fallback used:** ran `npx tsc --noEmit` via the PowerShell tool directly;
  output was empty (clean) so nothing was lost this time, but any noisy build
  would have dumped in full.
- **Suggested fix:** resolve the command with a PATHEXT-aware lookup on
  win32 (try `.cmd`, `.bat`, `.ps1`, `.exe`), or spawn via shell on Windows.
