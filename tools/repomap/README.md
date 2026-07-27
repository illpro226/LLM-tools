# repomap

Compact repository map generator: a pruned directory tree plus a
one-line-per-symbol outline of each source file's top-level
classes/functions, most-referenced files first. Lets an agent orient
itself in a repo for ~1–2k tokens instead of reading dozens of files.

```
./repomap.py [DIR]              map for a directory (default: cwd)
./repomap.py --focus PATH       outline only that file/subtree; every
                                other file collapses to one line
./repomap.py --max-tokens N     stay under a token budget (bytes/4),
                                degrading: collapse deep tree levels →
                                drop low-rank outlines → drop signatures
                                → tree-only
```

Every symbol line carries `path:line` so an entry can be followed up
with `xread PATH --symbol NAME`. Output is plain text and deterministic;
ranking is heuristic (identifier reference counts) and labeled as such.

Stdlib-only single file; `python -m pytest` from this directory runs the
tests. See [`PRD.md`](PRD.md) for scope and [`DECISIONS.md`](DECISIONS.md)
for the tree-sitter → stdlib deviation (ADR-004) and the deferred
`.repoindex` ranking source (ADR-005).
