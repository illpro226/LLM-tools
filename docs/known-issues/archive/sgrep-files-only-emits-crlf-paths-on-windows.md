# sgrep --files-only ends each path with CRLF on Windows, so a shell loop over it gets paths that do not exist

**RESOLVED 2026-10-09 (sgrep v0.7.0).** stdout is reconfigured with `newline="\n"`.

Filed 2026-10-06 from a bible-atlas session.

## What happened

In Git Bash on Windows, `--files-only` writes `\r\n` after every path. Command
substitution strips only the final newline, so every path but the last keeps a
trailing carriage return:

```
$ sgrep "use client" src/components/timeline --files-only | od -c | head -4
0000000   s   r   c   /   c   o   m   p   o   n   e   n   t   s   /   t
0000020   i   m   e   l   i   n   e   /   C   h   r   o   n   o   l   o
0000040   g   i   c   a   l   T   i   m   e   l   i   n   e   .   t   s
0000060   x  \r  \n   s   r   c   /   c   o   m   p   o   n   e   n   t

$ for f in $(sgrep "use client" src/components/timeline --files-only); do
>   test -f "$f" && echo "exists: $f" || echo "MISSING: [$f]" | cat -A; done
MISSING: [src/components/timeline/ChronologicalTimeline.tsx^M]$
exists: src/components/timeline/EraScrubber.tsx
```

Fed back into `sgrep` itself, the stray `\r` is an invalid Windows filename,
and the second call fails outright:

```
sgrep: rg failed: rg: src/components/dashboard/HeroPanel.tsx
: IO error for operation on src/components/dashboard/HeroPanel.tsx
: The filename, directory name, or volume label syntax is incorrect. (os error 123)
```

`--files-only` exists to be piped into the next command; this is the case it
is for, and it breaks silently for all but one file.

## Expected

Paths end with `\n` alone whatever the platform — the output is for a shell or
another tool, not a Windows text editor. (Probably the same `print` through a
text-mode stdout that turns `\n` into `\r\n`.)
