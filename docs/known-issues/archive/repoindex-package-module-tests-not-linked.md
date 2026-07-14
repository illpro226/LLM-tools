# repoindex: tests importing a package don't link to its internal modules

**RESOLVED 2026-07-11 (repoindex v0.1.5):** test seeding now links a
package-importing test to the package's `__init__.py` and to each module
named in `from pkg import mod` (directory-relative first, then a unique
repo-wide package match — the same fallback spirit as module imports).
On this repo's index, `test_repoindex.py` now links to `cli.py`,
`extract.py`, and `__init__.py`, and codediff no longer flags extract.py
as uncovered. Residuals: imports inside test *functions* are invisible to
the extractor (module-body imports only), and the cross-tool sys.path
import (codediff -> repoindex.extract) remains a documented limitation.

**What breaks:** codediff's risk block flagged `no known tests cover 1
changed file` for `tools/repoindex/repoindex/extract.py` — a file that is
in reality covered heavily by `tools/repoindex/tests/test_repoindex.py`
(which was even edited in the same change). The `tests` table has no row
linking them, so every consumer of that table (codediff risk flags,
`testmap`, `rq untested`) inherits the blind spot.

**When it happens:** the covered code is a module inside a package
(`repoindex/extract.py`) while the test file imports the package
(`from repoindex import cli, extract`). Convention linking matches stems
(`test_repoindex.py` -> `repoindex.py`, the entry point) and import-derived
linking resolves the import to the package, not to the internal modules
actually exercised. Same-session example: rq/testmap/codediff suites also
needed running after an `extract.py` change (codediff imports
`repoindex.extract` cross-tool via path manipulation), and nothing in the
index surfaces that either. Found 2026-07-10 during the v0.1.4 shadowing
fix.

**Expected:** a test file that imports package `p` should get `tests` rows
for `p/<module>.py` files too (or at least for the modules named in
`from p import x`), so file-level coverage questions don't report false
negatives. The cross-tool sys.path import is harder and may only deserve a
documented limitation.

**Workaround:** `testmap record -- pytest` writes exact coverage rows,
which supersede the convention/import layers — but it must be re-run per
repo and is pytest-only. Treat "no known tests cover X" as "no *link*
known", not "untested".
