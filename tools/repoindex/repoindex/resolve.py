"""Repo-wide resolution pass: only the indexer runs this, never extract().

Resolves raw refs against imports plus scope-aware name matching, tagging
confidence=resolved when a match is confirmed and confidence=heuristic for
everything else (unresolved names, ambiguous bare names, dynamic calls,
receiver-typed method calls we can't type-infer without tree-sitter/full
type inference). Also seeds the `tests` table (convention + import-derived)
and derives Go's structural `implements` edges (no explicit keyword in Go).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

_TEST_STEM_PATTERNS = {
    "python": [(r"^test_(.+)\.py$", 1), (r"^(.+)_test\.py$", 1)],
    "javascript": [(r"^(.+)\.test\.jsx?$", 1), (r"^(.+)\.spec\.jsx?$", 1)],
    "typescript": [(r"^(.+)\.test\.tsx?$", 1), (r"^(.+)\.spec\.tsx?$", 1)],
    "go": [(r"^(.+)_test\.go$", 1)],
}
_SOURCE_EXT = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "go": ".go",
}

_TEST_STEM_PATTERNS = {k: [(re.compile(p), g) for p, g in v]
                        for k, v in _TEST_STEM_PATTERNS.items()}


@dataclass
class ResolvedRef:
    file: str
    line: int
    to_name: str
    to_symbol: str | None
    kind: str
    confidence: str  # resolved | heuristic


@dataclass
class TestLink:
    test_file: str
    target_file: str
    source: str  # convention | import


def _local_index(ef):
    idx = {}
    for s in ef.symbols:
        local = s.qualname.split("::", 1)[1]
        idx[local] = s.qualname
    return idx


def build_indexes(files):
    """files: list[ExtractedFile]. Returns (by_file, by_dir, global_bare)."""
    by_file = {}
    by_dir = {}
    global_bare = {}
    for ef in files:
        local_idx = _local_index(ef)
        by_file[ef.path] = local_idx
        d = os.path.dirname(ef.path)
        by_dir.setdefault(d, {}).update(local_idx)
        for local, qn in local_idx.items():
            if "." not in local:
                global_bare.setdefault(local, []).append(qn)
    return by_file, by_dir, global_bare


def _py_candidates(importing_file, module_with_dots):
    level = len(module_with_dots) - len(module_with_dots.lstrip("."))
    rest = module_with_dots[level:]
    dir_ = os.path.dirname(importing_file)
    if level > 0:
        for _ in range(level - 1):
            dir_ = os.path.dirname(dir_)
    parts = [p for p in rest.split(".") if p]
    rel = "/".join(parts)
    candidates = []
    if dir_ and rel:
        candidates.append(f"{dir_}/{rel}.py")
    if rel:
        candidates.append(f"{rel}.py")
    return candidates


def _js_candidates(importing_file, module):
    if not module.startswith("."):
        return []
    dir_ = os.path.dirname(importing_file)
    base = os.path.normpath(f"{dir_}/{module}").replace("\\", "/")
    return [base, f"{base}.ts", f"{base}.tsx", f"{base}.js", f"{base}.jsx",
            f"{base}/index.ts", f"{base}/index.js"]


_go_module_cache = {}


def _find_go_module(root, start_dir):
    d = start_dir
    while True:
        key = (root, d)
        if key in _go_module_cache:
            cached = _go_module_cache[key]
        else:
            gomod = os.path.join(root, d, "go.mod") if d else os.path.join(root, "go.mod")
            cached = None
            if os.path.isfile(gomod):
                with open(gomod, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("module "):
                            cached = (d, line.split(None, 1)[1].strip())
                            break
            _go_module_cache[key] = cached
        if cached is not None:
            return cached
        parent = os.path.dirname(d)
        if parent == d or (parent == "" and d == ""):
            return (None, None)
        d = parent


def _go_target_dir(root, importing_file, module_path):
    if root is None:
        return None
    start_dir = os.path.dirname(importing_file)
    gomod_dir, mod_name = _find_go_module(root, start_dir)
    if mod_name is None:
        return None
    if module_path == mod_name:
        return gomod_dir
    prefix = mod_name + "/"
    if module_path.startswith(prefix):
        sub = module_path[len(prefix):]
        return f"{gomod_dir}/{sub}" if gomod_dir else sub
    return None


def _module_targets(ef, imp, root, by_file=None):
    if ef.language == "python":
        cands = [("file", c) for c in _py_candidates(ef.path, imp.module)]
        if by_file is not None and not any(c[1] in by_file for c in cands):
            # Directory-relative resolution failed -- fall back to a
            # repo-wide basename search (real layouts often rely on a
            # package root added to sys.path that we can't observe
            # statically, e.g. a tests/ dir importing from src/pkg).
            rel = imp.module.lstrip(".").replace(".", "/")
            if rel:
                suffix = f"/{rel}.py"
                matches = [p for p in by_file
                           if p == f"{rel}.py" or p.endswith(suffix)]
                if len(matches) == 1:
                    cands.append(("file", matches[0]))
        return cands
    if ef.language in ("javascript", "typescript"):
        return [("file", c) for c in _js_candidates(ef.path, imp.module)]
    if ef.language == "go":
        tdir = _go_target_dir(root, ef.path, imp.module)
        return [("dir", tdir)] if tdir is not None else []
    return []


def _import_key(ef, imp):
    if ef.language == "go":
        return imp.alias or imp.module.rsplit("/", 1)[-1]
    if imp.symbol is None:
        # Whole-module import: `import lib` binds "lib" (dotted modules bind
        # their first component, which partition-on-first-dot won't match --
        # those stay heuristic, same as before).
        return imp.alias or imp.module
    return imp.alias or imp.symbol


def resolve_refs(files, root=None):
    """Returns a flat list of ResolvedRef across every file."""
    by_file, by_dir, global_bare = build_indexes(files)
    imports_by_file = {ef.path: ef.imports for ef in files}
    out = []
    for ef in files:
        local_idx = by_file.get(ef.path, {})
        for ref in ef.refs:
            to_symbol, confidence = _resolve_one(
                ref.to_name, ef, local_idx, imports_by_file.get(ef.path, []),
                by_file, by_dir, global_bare, root)
            out.append(ResolvedRef(file=ref.file, line=ref.line,
                                    to_name=ref.to_name, to_symbol=to_symbol,
                                    kind=ref.kind, confidence=confidence))
    return out


def _resolve_one(name, ef, local_idx, imports, by_file, by_dir, global_bare, root):
    if name == "<dynamic>":
        return None, "heuristic"
    if name in local_idx:
        return local_idx[name], "resolved"

    base, dot, rest = name.partition(".")
    for imp in imports:
        if _import_key(ef, imp) != base:
            continue
        want = rest if dot else (imp.symbol or base)
        for kind, target in _module_targets(ef, imp, root, by_file):
            table = by_file if kind == "file" else by_dir
            if want in table.get(target, {}):
                return table[target][want], "resolved"
        return None, "heuristic"

    if dot:
        return None, "heuristic"

    candidates = global_bare.get(name, [])
    if len(candidates) == 1:
        return candidates[0], "resolved"
    return None, "heuristic"


# ------------------------------------------------------- test seeding ---

def _py_package_targets(ef, imp, by_file):
    """Files a package import covers: the package's __init__.py plus the
    module named by `from pkg import mod` when that name is itself a file.
    _py_candidates only tries pkg.py, so a test importing a real package
    (pkg/__init__.py) would otherwise produce no link at all (known-issue
    repoindex-package-module-tests-not-linked). Directory-relative first,
    then unique repo-wide — same spirit as _module_targets's basename
    fallback."""
    if ef.language != "python":
        return []
    rel = imp.module.lstrip(".").replace(".", "/")
    if not rel:
        return []
    init = f"{rel}/__init__.py"
    dir_ = os.path.dirname(ef.path)
    if dir_ and f"{dir_}/{init}" in by_file:
        packages = [f"{dir_}/{rel}"]
    elif init in by_file:
        packages = [rel]
    else:
        suffix = f"/{init}"
        packages = [p[: -len("/__init__.py")] for p in by_file
                    if p.endswith(suffix)]
        if len(packages) != 1:
            return []
    out = [f"{packages[0]}/__init__.py"]
    if imp.symbol and f"{packages[0]}/{imp.symbol}.py" in by_file:
        out.append(f"{packages[0]}/{imp.symbol}.py")
    return out


def _test_stem(path, lang):
    base = os.path.basename(path)
    for pattern, group in _TEST_STEM_PATTERNS.get(lang, []):
        m = pattern.match(base)
        if m:
            return m.group(group)
    return None


def seed_tests(files, root=None):
    """Convention (stem match, same language only) + import-derived links."""
    sources = {}  # (language, stem) -> [path] for non-test files
    tests = []  # (ExtractedFile, stem)
    for ef in files:
        if ef.language is None:
            continue
        stem = _test_stem(ef.path, ef.language)
        if stem is not None:
            tests.append((ef, stem))
        else:
            base = os.path.basename(ef.path)
            ext = _SOURCE_EXT.get(ef.language)
            if ext and base.endswith(ext):
                sources.setdefault((ef.language, base[: -len(ext)]), []).append(ef.path)

    by_file, by_dir, _ = build_indexes(files)
    links = []
    seen = set()
    for test_ef, stem in tests:
        import_targets = set()
        for imp in test_ef.imports:
            import_targets.update(
                _py_package_targets(test_ef, imp, by_file))
            for kind, target in _module_targets(test_ef, imp, root, by_file):
                table = by_file if kind == "file" else by_dir
                if target in table:
                    if kind == "file":
                        import_targets.add(target)
                    else:
                        import_targets.update(
                            f.path for f in files
                            if os.path.dirname(f.path) == target)
        for target_file in import_targets:
            key = (test_ef.path, target_file)
            if key not in seen:
                seen.add(key)
                links.append(TestLink(test_file=test_ef.path,
                                       target_file=target_file,
                                       source="import"))

        for target_file in sources.get((test_ef.language, stem), []):
            key = (test_ef.path, target_file)
            if key not in seen:
                seen.add(key)
                links.append(TestLink(test_file=test_ef.path,
                                       target_file=target_file,
                                       source="convention"))
    return links


# ------------------------------------------------- go structural implements ---

def go_structural_implements(files):
    """Interfaces vs. structs' method sets, same directory (package) only.

    Go has no `implements` keyword -- satisfaction is structural. This is a
    best-effort, name-only method-set comparison (a real implementation would
    also check signatures; ADR-007 accepts that gap), so results are always
    confidence=heuristic (ADR-003).
    """
    from .extract import Implement

    by_dir_ifaces = {}    # dir -> {iface_name: (file, line, {method_names})}
    by_dir_methods = {}   # dir -> {receiver_type: (file, {method_names})}

    for ef in files:
        if ef.language != "go":
            continue
        d = os.path.dirname(ef.path)
        for name, methods in ef.extra.get("go_interfaces", {}).items():
            by_dir_ifaces.setdefault(d, {})[name] = (ef.path, None, methods)
        for s in ef.symbols:
            local = s.qualname.split("::", 1)[1]
            if s.kind == "interface":
                path, _, methods = by_dir_ifaces.get(d, {}).get(local, (ef.path, None, set()))
                by_dir_ifaces.setdefault(d, {})[local] = (ef.path, s.line_start, methods)
            elif s.kind == "method" and "." in local:
                recv, meth = local.split(".", 1)
                entry = by_dir_methods.setdefault(d, {}).setdefault(recv, (ef.path, set()))
                entry[1].add(meth)
                by_dir_methods[d][recv] = (ef.path, entry[1])

    out = []
    for d, ifaces in by_dir_ifaces.items():
        recv_methods = by_dir_methods.get(d, {})
        for iface_name, (iface_path, iface_line, want) in ifaces.items():
            if not want:
                continue
            for recv, (recv_path, have) in recv_methods.items():
                if want <= have:
                    out.append(Implement(
                        file=recv_path, line=iface_line or 1,
                        symbol=f"{recv_path}::{recv}",
                        interface=f"{iface_path}::{iface_name}"))
    return out
