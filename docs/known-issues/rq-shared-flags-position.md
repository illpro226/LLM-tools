# rq: shared flags rejected before the subcommand

**RESOLVED 2026-07-10 (rq v0.1.1):** shared flags are now defined on the
top-level parser too (subparser copies use `argparse.SUPPRESS` defaults so
they don't clobber pre-subcommand values); both positions work and the
post-subcommand value wins. README.md documents this.

**What breaks:** `rq --no-update whouses NAME` exits 2 with "unrecognized
arguments: --no-update". The shared flags (`--root`, `--json`,
`--max-tokens`, `--no-update`, `--repoindex`) are defined on the subparsers
via a parent parser, so they are only accepted *after* the subcommand.

**When it happens:** first thing an agent types — global-looking flags
naturally go first (`git -C path log` style). Found on rq's first real-repo
use.

**Expected:** either accept the shared flags in both positions (define them
on the top-level parser too) or state the required position in README.md's
"Shared flags" paragraph.

**Workaround:** put flags after the subcommand: `rq whouses NAME --no-update`.
