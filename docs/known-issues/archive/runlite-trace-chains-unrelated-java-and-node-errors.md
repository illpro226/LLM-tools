# runlite trace chains unrelated Java and Node errors as "caused by"

**RESOLVED 2026-10-09 (runlite v0.6.0).** Java chains only on `Caused by:`/`Suppressed:`, Node only on `[cause]:` (real node 22 format, with its ` {` and elision lines).

Filed 2026-10-08 from a full-suite review session.

## What broke

Two unrelated Java exceptions in one log, with a normal log line between
them:

```
$ runlite trace app.log
# runlite trace: java, 1 trace, 3 frames (innermost first) [input 274 B]

java.lang.IllegalStateException: one
  A.java:10  in com.acme.A.run
  Main.java:5  in com.acme.Main.main
caused by  java.lang.NullPointerException: two
  B.java:20  in com.acme.B.go
```

The second exception was thrown on a different thread and did not cause the
first. Node output has the same shape: `TypeError: first failure` and a
later, unrelated `RangeError: second failure` come out as one trace with the
second labeled `caused by`.

## Why

`parse_java_trace` and `parse_node_trace` build a single trace and label
every section after the first `"caused by"`. Python had the same bug and was
fixed: a chain now needs the explicit relation marker, and anything else
starts a new trace (see the comment in `parse_python_trace`). The other two
parsers did not get that fix.

## What changed

Not fixed. Expected: Java starts a new trace at every `Exception in thread`
header or bare exception header, and chains only on `Caused by:` /
`Suppressed:`. Node starts a new trace for each header-plus-frames run, and
chains only on `[cause]:`.
