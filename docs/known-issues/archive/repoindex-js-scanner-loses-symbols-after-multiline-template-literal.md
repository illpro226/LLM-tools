# repoindex's JS scanner loses every symbol after a multi-line template literal

**RESOLVED 2026-10-09 (repoindex v0.1.7).** The template-literal state and `_template_close` are ported in. The four copies are still separate; the shared-scanner suggestion stays in STATUS.md Next.

Filed 2026-10-08 from a full-suite review session.
Affects codediff too, because it parses both sides through `repoindex.extract`.

## What broke

```js
const html = `
  <div>{</div>
`;
export function after() { return 1; }
```

```
>>> [s.qualname for s in extract("t.js", src, "javascript").symbols]
[]
```

`after` is missing, and so is every top-level declaration after it in the
file. `xread t.js --symbol after` on the same file finds it (`t.js:4-4`).

## Why

There are four copies of the JS "strip strings and comments" scanner:
xread, repomap, gitbrief and repoindex. The first three track a `template`
state, so a backtick that does not close on its line carries over, and the
`{` inside the literal is not counted. repoindex's `_strip_js_noise` never
got that fix. The brace in line 2 raises the depth to 1 and never comes back
down, so nothing after it is top level.

## What changed

Not fixed. Expected: port the template-literal handling (`_template_close`
plus the `state["template"]` toggle) into repoindex. Better, give the suite
one shared scanner so a fix lands everywhere. Each copy was "adapted from"
another, and this is the drift that produces.
