# structo types YAML booleans `yes`/`off`/`TRUE` as strings

**STATUS: open.** Filed 2026-10-08 from a full-suite review session. Minor.

## What broke

```yaml
enabled: yes
debug: off
strict: TRUE
```

```
$ structo flags.yaml
root: object
  enabled: str  100%  e.g. "yes"
  debug: str  100%  e.g. "off"
  strict: str  100%  e.g. "TRUE"
```

PyYAML, the parser structo depends on, loads all three as `bool`. `TRUE`
is a bool in YAML 1.2's core schema too. The schema contradicts what any
consumer of the file sees.

## Why

`yaml_events` reads raw scalar events and types plain scalars itself with
a short list: `true/false/True/False` for bools and `~/null/Null/NULL` for
nulls. PyYAML's resolver (YAML 1.1) also accepts `yes/no/on/off/y/n` in any
case, and `TRUE/FALSE`.

## What changed

Not fixed. Expected: classify plain scalars with PyYAML's own resolver
(`yaml.resolver.Resolver().resolve(yaml.ScalarNode, value, (True, False))`
returns the tag), so structo agrees with the loader by construction.
