# structo log templates label 8+ digit numbers as `<hex>`

**STATUS: open.** Filed 2026-10-08 from a full-suite review session. Minor.

## What broke

```
job 20240100 finished in 100 ms
job 20240101 finished in 101 ms
```

```
$ structo app.log
templates (top 1 of 1):
  5× job <hex> finished in <n> ms
```

Dates, epoch-millis, order numbers and other long decimal ids become
`<hex>`, which suggests a hash or address where there is a number.

## Why

`_HEX_RX` (`\b[0-9a-f]{8,}\b`) runs before `_NUM_RX` and matches any run
of 8+ decimal digits, since digits are hex characters.

## What changed

Not fixed. Expected: require at least one `a-f` letter in a hex match
(`\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,}\b`), so pure-digit runs fall through to
`<n>`.
