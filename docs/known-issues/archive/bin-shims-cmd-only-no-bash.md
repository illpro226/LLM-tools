# bin/ shims: `.cmd` only, so bash shells can't call tools by bare name

**RESOLVED 2026-07-11:** `bin/` now carries an extensionless `#!/bin/sh`
shim alongside each `.cmd` (`exec python "$(dirname "$0")/../tools/<name>/<name>.py" "$@"`).
Verified both directions: Git Bash resolves the sh shims by bare name
(`xread`, `tokq`, `rq` all ran), and PowerShell still picks the `.cmd`
via PATHEXT (`(Get-Command xread).Source` → `xread.cmd`). The repo-wide
`* text=auto eol=lf` gitattributes rule already checks the sh shims out
with LF; only `.cmd`/`.bat` get CRLF.

- **What breaks:** with only `.cmd` shims on PATH, any POSIX shell (Git
  Bash, WSL) gets `command not found` for every tool by bare name —
  bash does not resolve `.cmd` files. Hit in a real session 2026-07-11:
  `xread START.md --headings` failed in the Bash tool while working in
  PowerShell.
- **Impact:** agents (or humans) working in a bash shell had to fall
  back to `python G:/.../tools/<name>/<name>.py`, defeating the
  bare-name adoption path AGENTS.md documents.
- **Why it happened:** the shims were created for the Windows PATH
  mechanism only; MSYS/Git Bash inherits the same PATH entries but uses
  POSIX executable resolution.
