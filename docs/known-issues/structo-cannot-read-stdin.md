# structo cannot read stdin

**Date:** 2026-10-06
**Found in:** bible-atlas, while inspecting an API response

## What happened

```
$ curl -s "http://localhost:3010/api/v1/search?q=Carmel&limit=3" | structo -
structo: not a file: -
```

The hook steers inline JSON parsing (`node -e "JSON.parse(...)"`) to
`structo`. But a JSON body that only exists as a command's output, such as an
API response, has to be written to a scratch file first. That's two calls
where one would do.

## Expected

`structo -` (or `structo` with no path and piped input) reads stdin. Infer the
format from content, or take `--format json|yaml|xml`.
