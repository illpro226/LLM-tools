# xread

Targeted code excerpt reader: prints just the relevant parts of a file —
a named symbol's body, a line range expanded to its enclosing scope, the
top blocks for a keyword query, or a markdown section — replacing most
whole-file reads.

Single-file Python CLI, stdlib only. Python is parsed with `ast` (exact
spans, decorators and attached comments included); JS/TS with a
brace-tracking heuristic scanner; markdown headings are treated as just
another symbol kind; Prisma schema blocks (`model`, `enum`, `type`,
`view`, `generator`, `datasource`) with a flat block scanner.

## Usage

```
xread FILE --symbol NAME          # function/class/method body; nested
                                  # names like ClassName.method; on .md
                                  # files, a heading's section
xread FILE --lines A-B [--scope]  # line range; --scope expands to the
                                  # enclosing function/class
xread FILE --query "text" [--top N]   # top keyword-scoring blocks
xread FILE.md --headings          # markdown heading outline
```

All modes accept multiple files (grouped in argument order) and
`--max-tokens N`, which degrades by dropping whole low-score blocks and
trimming at blank-line boundaries — never mid-statement.

### Example

```
$ xread tools/tokq/tokq.py --lines 120-121 --scope
== tools/tokq/tokq.py:120-128 ==
def _shannon_entropy(data):
    if not data:
        return 0.0
    ...
```

Every excerpt starts with a citable `== path:start-end ==` header;
`… N lines elided …` markers appear between non-adjacent excerpts, and
overlapping requests are merged so no line is ever printed twice.

## Development

```
python -m pytest        # from tools/xread/
```

Fixtures live in `tests/fixtures/` (`big.py` is generated but committed).
See the repo root `START.md` for suite-wide conventions.
