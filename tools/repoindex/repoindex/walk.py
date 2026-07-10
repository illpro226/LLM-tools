"""Repo file discovery: skip-list + root .gitignore, recognized extensions only."""
from __future__ import annotations

import fnmatch
import os

SKIP_DIRS = {".git", ".repoindex", "node_modules", "__pycache__",
             ".venv", "venv", "vendor", "dist", "build",
             ".pytest_cache", ".mypy_cache"}
EXTS = (".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go")


def load_gitignore(root):
    path = os.path.join(root, ".gitignore")
    pats = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    pats.append(line)
    return pats


def ignored(rel, name, pats):
    for pat in pats:
        p = pat.rstrip("/")
        if (fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p)
                or fnmatch.fnmatch(rel, f"*/{p}")):
            return True
    return False


def scan_repo(root):
    """Returns sorted repo-relative (forward-slash) paths of source files."""
    pats = load_gitignore(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                        if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(EXTS):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if ignored(rel, name, pats):
                continue
            out.append(rel)
    out.sort()
    return out


def ensure_gitignore_entry(root):
    """Adds `.repoindex/` to root .gitignore if not already covered."""
    path = os.path.join(root, ".gitignore")
    existing = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read().splitlines()
    for line in existing:
        s = line.strip()
        if s in (".repoindex/", ".repoindex", "/.repoindex/", "/.repoindex"):
            return False
    with open(path, "a", encoding="utf-8") as f:
        if existing and existing[-1].strip():
            f.write("\n")
        f.write(".repoindex/\n")
    return True
