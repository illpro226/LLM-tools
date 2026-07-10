"""Pure, filesystem-free extraction: extract(path, source) -> ExtractedFile.

ADR-006: no filesystem, git, or database access happens in this module.
`source` is the content to parse; `path` is a label and language hint only.
Refs are raw (unresolved) names -- a separate repo-wide pass resolves them
against imports and scope (see resolve.py). Stdlib parsers only (ADR-007):
Python via `ast` (exact spans), JS/TS and Go via heuristic line/brace
scanners adapted from xread/repomap.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
}


def detect_language(path, source=None):
    """Extension-based language detection. Separate, overridable step."""
    for ext, lang in _LANG_BY_EXT.items():
        if path.endswith(ext):
            return lang
    return None


@dataclass
class Symbol:
    qualname: str
    kind: str  # func | method | class | const | type | interface
    file: str
    line_start: int
    line_end: int
    exported: bool


@dataclass
class Ref:
    file: str
    line: int
    to_name: str  # raw name, unresolved; "<dynamic>" for duck-typed calls
    kind: str  # call | read | write | type-use


@dataclass
class Import:
    file: str
    line: int
    module: str
    symbol: str | None  # None for whole-module imports
    alias: str | None


@dataclass
class Inherit:
    file: str
    line: int
    child: str  # qualname
    parent: str  # raw name, unresolved


@dataclass
class Implement:
    file: str
    line: int
    symbol: str  # qualname
    interface: str  # raw name, unresolved


@dataclass
class ExtractedFile:
    path: str
    language: str | None
    symbols: list = field(default_factory=list)
    refs: list = field(default_factory=list)
    imports: list = field(default_factory=list)
    inherits: list = field(default_factory=list)
    implements: list = field(default_factory=list)
    # Language-specific side data not part of the shared schema -- currently
    # just Go's {interface_name: {method_names}}, used by resolve.py to do a
    # real (if name-only) structural-satisfaction check instead of a vacuous
    # same-directory match.
    extra: dict = field(default_factory=dict)


def extract(path, source, lang=None):
    """Pure extraction entry point. No I/O -- source is already in hand."""
    lang = lang or detect_language(path, source)
    if lang == "python":
        return _extract_python(path, source)
    if lang in ("javascript", "typescript"):
        return _extract_ts(path, source, lang)
    if lang == "go":
        return _extract_go(path, source)
    return ExtractedFile(path=path, language=lang)


# --------------------------------------------------------------- python ---

def _dotted(node):
    """Best-effort dotted name for a Name/Attribute chain; None otherwise."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _end_line(node, fallback):
    return getattr(node, "end_lineno", None) or fallback


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.symbols = []
        self.refs = []
        self.imports = []
        self.inherits = []
        self.implements = []
        self._abstract_classes = set()  # qualnames known to be ABC-derived
        self._module_vars = set()  # top-level simple-assignment names

    def qualname(self, *parts):
        return self.path + "::" + ".".join(parts)

    # -- imports --
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(Import(
                file=self.path, line=node.lineno,
                module=alias.name, symbol=None, alias=alias.asname))

    def visit_ImportFrom(self, node):
        module = ("." * (node.level or 0)) + (node.module or "")
        for alias in node.names:
            self.imports.append(Import(
                file=self.path, line=node.lineno,
                module=module, symbol=alias.name, alias=alias.asname))

    # -- module-level state (collected before body walk) --
    def _collect_module_vars(self, body):
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        self._module_vars.add(t.id)
            elif isinstance(stmt, (ast.AnnAssign,)) and isinstance(stmt.target, ast.Name):
                self._module_vars.add(stmt.target.id)

    def visit_Module(self, node):
        self._collect_module_vars(node.body)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        self.symbols.append(Symbol(
                            qualname=self.qualname(t.id), kind="const",
                            file=self.path, line_start=stmt.lineno,
                            line_end=_end_line(stmt, stmt.lineno),
                            exported=not t.id.startswith("_")))
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                self._collect_stmt_refs(stmt)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._visit_func(node, "func")

    def visit_AsyncFunctionDef(self, node):
        self._visit_func(node, "func")

    def _visit_func(self, node, kind):
        self.symbols.append(Symbol(
            qualname=self.qualname(node.name), kind=kind, file=self.path,
            line_start=node.lineno, line_end=_end_line(node, node.lineno),
            exported=not node.name.startswith("_")))
        self._collect_refs(node)

    def visit_ClassDef(self, node):
        qn = self.qualname(node.name)
        self.symbols.append(Symbol(
            qualname=qn, kind="class", file=self.path,
            line_start=node.lineno, line_end=_end_line(node, node.lineno),
            exported=not node.name.startswith("_")))

        is_abstract = any(_dotted(b) in ("ABC",) for b in node.bases) or any(
            isinstance(d, ast.Call) and _dotted(d.func) == "abstractmethod"
            for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            for d in m.decorator_list
        )
        for base in node.bases:
            name = _dotted(base)
            if not name or name == "ABC":
                continue
            local = name.split(".")[-1]
            if local in self._abstract_classes:
                self.implements.append(Implement(
                    file=self.path, line=node.lineno, symbol=qn, interface=name))
            else:
                self.inherits.append(Inherit(
                    file=self.path, line=node.lineno, child=qn, parent=name))
        if is_abstract:
            self._abstract_classes.add(node.name)

        for dec in node.decorator_list:
            self._collect_stmt_refs(dec)
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mqn = self.qualname(node.name, member.name)
                self.symbols.append(Symbol(
                    qualname=mqn, kind="method", file=self.path,
                    line_start=member.lineno,
                    line_end=_end_line(member, member.lineno),
                    exported=not member.name.startswith("_")))
                self._collect_refs(member)
            else:
                self._collect_stmt_refs(member)

    def _add_call_ref(self, node, shadowed=frozenset()):
        func = node.func
        if isinstance(func, ast.Name) and func.id in shadowed:
            # Call through a name bound in the enclosing function (local
            # assignment, parameter, nested def, ...): the static name says
            # nothing about the target, so treat it like any other dynamic
            # call instead of letting the resolve pass bind it to an
            # unrelated repo-wide symbol as `resolved`.
            self.refs.append(Ref(file=self.path, line=node.lineno,
                                  to_name="<dynamic>", kind="call"))
        elif isinstance(func, (ast.Name, ast.Attribute)):
            self.refs.append(Ref(file=self.path, line=node.lineno,
                                  to_name=_dotted(func), kind="call"))
        else:
            self.refs.append(Ref(file=self.path, line=node.lineno,
                                  to_name="<dynamic>", kind="call"))

    def _collect_stmt_refs(self, stmt):
        """Refs from code that runs at import time (module and class bodies).
        Does not descend into nested def/class bodies -- those are collected
        by their own visitors, so descending would double-count."""
        stack = [stmt]
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                continue
            if isinstance(node, ast.Call):
                self._add_call_ref(node)
            elif (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id in self._module_vars):
                self.refs.append(Ref(file=self.path, line=node.lineno,
                                      to_name=node.id, kind="read"))
            stack.extend(reversed(list(ast.iter_child_nodes(node))))

    def _collect_refs(self, func_node):
        # Names bound inside the function shadow module/repo symbols for the
        # whole body (Python scoping). Over-approximated across nested scopes
        # (comprehensions, inner defs) -- erring toward heuristic, never
        # toward a false `resolved`. Import bindings are deliberately left
        # out: they bind the real symbol, so the bare-name fallback is right.
        globals_declared = set()
        shadowed = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Global):
                globals_declared.update(node.names)
            elif isinstance(node, ast.Nonlocal):
                shadowed.update(node.names)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                shadowed.add(node.id)
            elif isinstance(node, ast.arg):
                shadowed.add(node.arg)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                shadowed.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)) and node is not func_node:
                shadowed.add(node.name)
        shadowed -= globals_declared

        for node in ast.walk(func_node):
            if node is func_node:
                continue
            if isinstance(node, ast.Call):
                self._add_call_ref(node, shadowed)
            elif isinstance(node, ast.Name):
                if node.id in globals_declared or (
                        node.id in self._module_vars
                        and node.id not in shadowed):
                    kind = "write" if isinstance(node.ctx, ast.Store) else "read"
                    self.refs.append(Ref(file=self.path, line=node.lineno,
                                          to_name=node.id, kind=kind))
            elif isinstance(node, (ast.arg,)) and node.annotation is not None:
                name = _dotted(node.annotation)
                if name:
                    self.refs.append(Ref(file=self.path, line=node.lineno,
                                          to_name=name, kind="type-use"))
        if getattr(func_node, "returns", None) is not None:
            name = _dotted(func_node.returns)
            if name:
                self.refs.append(Ref(file=self.path, line=func_node.lineno,
                                      to_name=name, kind="type-use"))


def _extract_python(path, source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ExtractedFile(path=path, language="python")
    visitor = _PyVisitor(path)
    visitor.visit(tree)
    return ExtractedFile(
        path=path, language="python", symbols=visitor.symbols,
        refs=visitor.refs, imports=visitor.imports,
        inherits=visitor.inherits, implements=visitor.implements)


# --------------------------------------------------------- js/ts scanner ---
# Adapted from xread/repomap: strings and comments are stripped so brace
# counting sees only code; declarations are recognized at brace depth 0.

def _strip_js_noise(line, state):
    out = []
    i, n = 0, len(line)
    while i < n:
        if state["comment"]:
            end = line.find("*/", i)
            if end == -1:
                return "".join(out)
            state["comment"] = False
            i = end + 2
            continue
        ch = line[i]
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if ch == "/" and i + 1 < n and line[i + 1] == "*":
            state["comment"] = True
            i += 2
            continue
        if ch in "'\"`":
            quote, j = ch, i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == quote:
                    break
                j += 1
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_TS_CLASS = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+"
    r"([A-Za-z_$][\w$]*)"
    r"(?:\s+extends\s+([A-Za-z_$][\w$.]*))?"
    r"(?:\s+implements\s+([A-Za-z_$][\w$.,\s]*))?")
_TS_INTERFACE = re.compile(
    r"^(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)"
    r"(?:\s+extends\s+([A-Za-z_$][\w$.,\s]*))?")
_TS_FUNC = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*"
    r"([A-Za-z_$][\w$]*)")
_TS_CONST_FUNC = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
    r"[^=;]*=\s*(?:async\b[^=;]*)?(?:\([^)]*\)?|[A-Za-z_$][\w$]*)"
    r"\s*(?::[^=]*)?=>")
_TS_METHOD = re.compile(
    r"^(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*"
    r"([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[\w$.<>\[\]| ]+)?\s*\{")
_TS_IMPORT_NAMED = re.compile(
    r"^import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]")
_TS_IMPORT_DEFAULT = re.compile(
    r"^import\s+([A-Za-z_$][\w$]*)\s+from\s+['\"]([^'\"]+)['\"]")
_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
_JS_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "function", "return",
    "typeof", "new", "in", "of", "do", "else", "super",
}


def _split_names(blob):
    return [n.strip().split(" as ")[0].strip()
            for n in blob.split(",") if n.strip()]


def _split_import_names(blob):
    """Named-import list, alias-aware: 'Square as Sq' -> ('Square', 'Sq')."""
    out = []
    for part in blob.split(","):
        part = part.strip()
        if not part:
            continue
        if " as " in part:
            orig, alias = part.split(" as ", 1)
            out.append((orig.strip(), alias.strip()))
        else:
            out.append((part, None))
    return out


def _extract_ts(path, source, lang):
    lines = source.splitlines()
    symbols, refs, imports, inherits, implements = [], [], [], [], []
    depth = 0
    class_stack = []  # (qualname, end-detection depth)
    state = {"comment": False}

    for i, raw in enumerate(lines, 1):
        # Import paths are string literals -- match them against the raw
        # line, not the noise-stripped one (which deletes string contents).
        line = raw.strip()
        m = _TS_IMPORT_NAMED.match(line)
        if m:
            for name, alias in _split_import_names(m.group(1)):
                imports.append(Import(file=path, line=i, module=m.group(2),
                                       symbol=name, alias=alias))
        else:
            m = _TS_IMPORT_DEFAULT.match(line)
            if m:
                imports.append(Import(file=path, line=i, module=m.group(2),
                                       symbol=None, alias=m.group(1)))

        code = _strip_js_noise(raw, state).strip()
        if not code:
            # Line is all comment/string noise -- any braces on it are
            # inside that noise and must not move the depth counter.
            continue

        declared_name = None  # this line's own declared name, if any --
        # excluded from call-ref scanning below so a declaration line
        # (e.g. "function buildShapes() {") isn't also read as a call.
        if depth == 0:
            m = _TS_CLASS.match(code)
            if m:
                name = m.group(1)
                declared_name = name
                qn = f"{path}::{name}"
                symbols.append(Symbol(qualname=qn, kind="class", file=path,
                                       line_start=i, line_end=i,
                                       exported="export" in code))
                if m.group(2):
                    inherits.append(Inherit(file=path, line=i, child=qn,
                                             parent=m.group(2)))
                if m.group(3):
                    for iface in _split_names(m.group(3)):
                        implements.append(Implement(file=path, line=i,
                                                      symbol=qn, interface=iface))
                class_stack.append((name, depth))
            else:
                m = _TS_INTERFACE.match(code)
                if m:
                    name = m.group(1)
                    declared_name = name
                    qn = f"{path}::{name}"
                    symbols.append(Symbol(qualname=qn, kind="interface",
                                           file=path, line_start=i, line_end=i,
                                           exported="export" in code))
                    if m.group(2):
                        for parent in _split_names(m.group(2)):
                            inherits.append(Inherit(file=path, line=i,
                                                     child=qn, parent=parent))
                else:
                    m = _TS_FUNC.match(code) or _TS_CONST_FUNC.match(code)
                    if m:
                        declared_name = m.group(1)
                        qn = f"{path}::{m.group(1)}"
                        symbols.append(Symbol(qualname=qn, kind="func",
                                               file=path, line_start=i,
                                               line_end=i,
                                               exported="export" in code))
        elif class_stack and depth == class_stack[-1][1] + 1:
            m = _TS_METHOD.match(code)
            if m and m.group(1) not in ("if", "for", "while", "switch", "constructor"):
                declared_name = m.group(1)
                cname = class_stack[-1][0]
                qn = f"{path}::{cname}.{m.group(1)}"
                symbols.append(Symbol(qualname=qn, kind="method", file=path,
                                       line_start=i, line_end=i,
                                       exported=True))
            elif m and m.group(1) == "constructor":
                declared_name = "constructor"

        for call in _CALL_RE.finditer(code):
            name = call.group(1)
            if name in _JS_KEYWORDS or name == declared_name:
                continue
            refs.append(Ref(file=path, line=i, to_name=name, kind="call"))

        new_depth = depth + code.count("{") - code.count("}")
        while class_stack and new_depth <= class_stack[-1][1]:
            class_stack.pop()
        depth = max(0, new_depth)

    return ExtractedFile(path=path, language=lang, symbols=symbols,
                          refs=refs, imports=imports, inherits=inherits,
                          implements=implements)


# ------------------------------------------------------------ go scanner ---
# Adapted from repomap: column-0 declarations only (gofmt-guaranteed).

_GO_FUNC = re.compile(
    r"^func\s+(?:\(\s*\w*\s+\*?([A-Za-z_]\w*)\s*\)\s*)?([A-Za-z_]\w*)\s*\(")
_GO_TYPE = re.compile(r"^type\s+([A-Za-z_]\w*)\s+(struct|interface)\b")
_GO_TYPE_ALIAS = re.compile(r"^type\s+([A-Za-z_]\w*)\s")
_GO_VAR = re.compile(r"^(var|const)\s+([A-Za-z_]\w*)")
_GO_IMPORT_SINGLE = re.compile(r'^import\s+(?:(\w+)\s+)?"([^"]+)"')
_GO_IMPORT_LINE = re.compile(r'^\s*(?:(\w+)\s+)?"([^"]+)"')
_GO_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)(\.[A-Za-z_]\w*)?\s*\(")
_GO_KEYWORDS = {"if", "for", "switch", "return", "range", "go", "defer",
                "select", "case", "func"}


_GO_IFACE_METHOD = re.compile(r"^([A-Za-z_]\w*)\s*\(")


def _extract_go(path, source):
    lines = source.splitlines()
    symbols, refs, imports = [], [], []
    go_interfaces = {}
    in_import_block = False
    current_func = None  # (qualname, receiver_type_or_None)

    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        code = raw.split("//", 1)[0]

        if in_import_block:
            if stripped.startswith(")"):
                in_import_block = False
                continue
            m = _GO_IMPORT_LINE.match(stripped)
            if m:
                imports.append(Import(file=path, line=i, module=m.group(2),
                                       symbol=None, alias=m.group(1)))
            continue
        if stripped.startswith("import ("):
            in_import_block = True
            continue
        m = _GO_IMPORT_SINGLE.match(stripped)
        if m:
            imports.append(Import(file=path, line=i, module=m.group(2),
                                   symbol=None, alias=m.group(1)))
            continue

        if raw[:1] in (" ", "\t"):
            if current_func:
                for call in _GO_CALL_RE.finditer(code):
                    first, second = call.group(1), call.group(2)
                    if first in _GO_KEYWORDS:
                        continue
                    name = f"{first}{second}" if second else first
                    refs.append(Ref(file=path, line=i, to_name=name,
                                    kind="call"))
            continue

        m = _GO_FUNC.match(stripped)
        if m:
            receiver, fname = m.group(1), m.group(2)
            if receiver:
                qn = f"{path}::{receiver}.{fname}"
                symbols.append(Symbol(qualname=qn, kind="method", file=path,
                                       line_start=i, line_end=i,
                                       exported=fname[:1].isupper()))
            else:
                qn = f"{path}::{fname}"
                symbols.append(Symbol(qualname=qn, kind="func", file=path,
                                       line_start=i, line_end=i,
                                       exported=fname[:1].isupper()))
            current_func = (qn, receiver)
            continue

        current_func = None
        m = _GO_TYPE.match(stripped)
        if m:
            name, kind = m.group(1), m.group(2)
            qn = f"{path}::{name}"
            symbols.append(Symbol(qualname=qn, kind=kind, file=path,
                                   line_start=i, line_end=i,
                                   exported=name[:1].isupper()))
            if kind == "interface":
                methods = set()
                for follow in lines[i:]:
                    fs = follow.strip()
                    if fs.startswith("}"):
                        break
                    mm = _GO_IFACE_METHOD.match(fs)
                    if mm:
                        methods.add(mm.group(1))
                go_interfaces[name] = methods
            continue
        m = _GO_TYPE_ALIAS.match(stripped)
        if m:
            name = m.group(1)
            qn = f"{path}::{name}"
            symbols.append(Symbol(qualname=qn, kind="type", file=path,
                                   line_start=i, line_end=i,
                                   exported=name[:1].isupper()))
            continue
        m = _GO_VAR.match(stripped)
        if m:
            kw, name = m.group(1), m.group(2)
            qn = f"{path}::{name}"
            symbols.append(Symbol(qualname=qn, kind=kw, file=path,
                                   line_start=i, line_end=i,
                                   exported=name[:1].isupper()))

    return ExtractedFile(path=path, language="go", symbols=symbols,
                          refs=refs, imports=imports,
                          extra={"go_interfaces": go_interfaces} if go_interfaces else {})
