#!/usr/bin/env python3
"""structo — schema and shape of a data file instead of its content.

    structo FILE              summarize (format auto-detected)
    structo FILE --path a.b[0].c   zoom into a JSON/YAML/TOML subtree
                              (a leading [N] picks JSONL record N;
                               [-1] is the last record)
    structo FILE --raw --path ...  print the exact value at --path
                              (strings verbatim, else JSON)
    structo FILE --select a,b.c    project fields out of every record as
                              TSV, one row per record, for piping to
                              awk/sort (never into context)
    structo FILE --sample N   elements aggregated per array (default 10)
    structo FILE --max-tokens N    cap output (bytes/4), degrading:
                              drop samples/examples -> collapse deep
                              nesting and distribution detail ->
                              top-level structure only (never dropped)

Formats: JSON, JSONL, YAML (needs PyYAML), TOML, CSV, TSV, XML, generic log.
Detection is by extension, else content sniffing; the header states which.

Everything is streamed — memory is O(schema + samples), never O(file):
JSON via an incremental event tokenizer, JSONL per record, YAML via the
PyYAML event API, CSV/logs per row/line, XML via iterparse with
element clearing. TOML is the one exception (ADR-008): tomllib has no
event API, so the document is parsed whole — config-file sized by
construction. Figures affected by sampling carry a `~` marker;
clean figures are exact (see DECISIONS.md ADR-003 — sampling is
first-N, deterministic).
"""

import argparse
import collections
import csv
import datetime
import itertools
import json
import os
import re
import sys

__version__ = "0.6.1"

DEFAULT_SAMPLE = 10
# ADR-006: schema output is capped by default; --select/--raw are not.
DEFAULT_MAX_TOKENS = 2000
EXAMPLES_PER_NODE = 2
EXAMPLE_CAP = 24
DISTINCT_CAP = 256
SAMPLE_ROWS = 3
TOP_TEMPLATES = 5
TEMPLATE_CAP = 512

EXT_FORMATS = {".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl",
               ".yaml": "yaml", ".yml": "yaml", ".csv": "csv",
               ".tsv": "tsv", ".xml": "xml", ".log": "log",
               ".toml": "toml"}
# Formats whose value model is a JSON-ish tree, so --path/--raw address them.
TREE_FORMATS = ("json", "jsonl", "yaml", "toml")
# Every text read decodes as utf-8-sig: identical to utf-8 on a file without
# a byte-order mark, and it drops the one Windows tools (Excel's "CSV UTF-8",
# PowerShell 5's Out-File) put in front. Left in, the BOM glued itself to
# the first CSV header — `--select id` then matched nothing and printed an
# empty column — and made JSONL record 0 unparsable, so `[0]` answered with
# record 1. Both silent. (Output streams stay plain utf-8: a BOM there
# would be written, not dropped.)
TEXT_ENCODING = "utf-8-sig"


class StructoError(Exception):
    pass


def _est(lines):
    return sum(len(l.encode("utf-8", "replace")) + 1 for l in lines) // 4


def fit(levels, budget):
    """First (most detailed) level within budget, else the last."""
    lines = levels[0]()
    if not budget or _est(lines) <= budget:
        return lines
    for level in levels[1:]:
        lines = level()
        if _est(lines) <= budget:
            return lines
    return lines


# ------------------------------------------------------- json event stream
# Events: ("{",) ("}",) ("[",) ("]",) ("key", text) ("scalar", type, text)

_UNESCAPE = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
             "n": "\n", "r": "\r", "t": "\t"}


def json_events(fh, full=False):
    """full=False caps strings at 64 chars and keeps escapes undecoded —
    enough for schema examples. full=True decodes escapes (incl. \\uXXXX
    surrogate pairs) and keeps whole strings, for --raw extraction."""
    stack = []
    expect_key = False
    mode = 0          # 0 normal, 1 string, 2 number/literal, 3 \uXXXX
    esc = False
    sbuf, slen = [], 0
    ubuf = []
    abuf = []
    out = []

    def end_container(tok):
        nonlocal expect_key
        if stack:
            stack.pop()
        out.append((tok,))
        if stack and stack[-1] == "o":
            expect_key = True

    def end_atom():
        nonlocal mode, expect_key
        text = "".join(abuf)
        abuf.clear()
        mode = 0
        if text in ("true", "false"):
            kind = "bool"
        elif text == "null":
            kind = "null"
        elif any(c in text for c in ".eE"):
            kind = "float"
        else:
            kind = "int"
        out.append(("scalar", kind, text))
        if stack and stack[-1] == "o":
            expect_key = True

    def normal(ch):
        nonlocal mode, expect_key, slen
        if ch == '"':
            mode = 1
            sbuf.clear()
            slen = 0
        elif ch == "{":
            out.append(("{",))
            stack.append("o")
            expect_key = True
        elif ch == "}":
            end_container("}")
        elif ch == "[":
            out.append(("[",))
            stack.append("a")
        elif ch == "]":
            end_container("]")
        elif ch in "-0123456789tfn":
            mode = 2
            abuf.append(ch)
        # whitespace, ',' and ':' are structure we do not need

    while True:
        chunk = fh.read(65536)
        if not chunk:
            break
        for ch in chunk:
            if mode == 1:
                if esc:
                    esc = False
                    if full:
                        if ch == "u":
                            mode = 3
                            ubuf.clear()
                        else:
                            sbuf.append(_UNESCAPE.get(ch, ch))
                    else:
                        if slen < 64:
                            sbuf.append(ch)
                        slen += 1
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    mode = 0
                    text = "".join(sbuf)
                    if stack and stack[-1] == "o" and expect_key:
                        out.append(("key", text))
                        expect_key = False
                    else:
                        out.append(("scalar", "str", text))
                        if stack and stack[-1] == "o":
                            expect_key = True
                else:
                    if full or slen < 64:
                        sbuf.append(ch)
                    slen += 1
            elif mode == 2:
                if ch in "+-.eE0123456789truefalsn":
                    abuf.append(ch)
                else:
                    end_atom()
                    normal(ch)
            elif mode == 3:
                ubuf.append(ch)
                if len(ubuf) == 4:
                    mode = 1
                    try:
                        cp = int("".join(ubuf), 16)
                    except ValueError:
                        cp = 0xFFFD
                    if 0xDC00 <= cp <= 0xDFFF and sbuf \
                            and 0xD800 <= ord(sbuf[-1]) <= 0xDBFF:
                        hi = ord(sbuf[-1])       # pair with high surrogate
                        sbuf[-1] = chr(0x10000 + ((hi - 0xD800) << 10)
                                       + (cp - 0xDC00))
                    else:
                        sbuf.append(chr(cp))
            else:
                normal(ch)
            if out:
                yield from out
                out.clear()
    if mode == 2:
        end_atom()
        yield from out


def value_events(value):
    """Synthesize the same event stream from a parsed (JSONL) record."""
    if isinstance(value, dict):
        yield ("{",)
        for k, v in value.items():
            yield ("key", str(k))
            yield from value_events(v)
        yield ("}",)
    elif isinstance(value, list):
        yield ("[",)
        for v in value:
            yield from value_events(v)
        yield ("]",)
    elif isinstance(value, bool):
        yield ("scalar", "bool", "true" if value else "false")
    elif isinstance(value, int):
        yield ("scalar", "int", str(value))
    elif isinstance(value, float):
        yield ("scalar", "float", repr(value))
    elif value is None:
        yield ("scalar", "null", "null")
    elif isinstance(value, (datetime.datetime, datetime.date,
                            datetime.time)):
        # TOML has first-class dates; calling them `str` would hide the one
        # thing that makes them worth knowing about.
        yield ("scalar", "datetime", value.isoformat())
    else:
        yield ("scalar", "str", str(value))


def toml_value(path):
    """The whole TOML document as a Python value.

    Unlike every other format, this is not streamed: tomllib exposes no
    event API, and TOML is a config format — files are kilobytes, not the
    multi-gigabyte logs the streaming promise exists for (ADR-008)."""
    try:
        import tomllib
    except ImportError:                                   # Python < 3.11
        try:
            import tomli as tomllib
        except ImportError:
            raise StructoError("toml support needs Python 3.11+ (tomllib) "
                               "or tomli (pip install tomli)")
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        # tomllib.load decodes strict utf-8 itself: a BOM fails as "Invalid
        # statement", and non-utf-8 bytes escape as a UnicodeDecodeError
        # traceback — even from the sniff that only guessed this was toml.
        return tomllib.loads(data.decode(TEXT_ENCODING))
    except UnicodeDecodeError as exc:
        raise StructoError("%s is not valid toml: not utf-8 (%s)"
                           % (path, exc.reason))
    except tomllib.TOMLDecodeError as exc:
        raise StructoError("%s is not valid toml: %s" % (path, exc))


_YAML_INT = re.compile(r"^[+-]?\d+$")
_YAML_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


def yaml_events(fh):
    try:
        import yaml
    except ImportError:
        raise StructoError("yaml support needs PyYAML "
                           "(pip install pyyaml)")
    stack = []
    expect_key = False
    for ev in yaml.parse(fh):
        if isinstance(ev, yaml.MappingStartEvent):
            yield ("{",)
            stack.append("o")
            expect_key = True
        elif isinstance(ev, yaml.MappingEndEvent):
            stack.pop()
            yield ("}",)
            if stack and stack[-1] == "o":
                expect_key = True
        elif isinstance(ev, yaml.SequenceStartEvent):
            yield ("[",)
            stack.append("a")
        elif isinstance(ev, yaml.SequenceEndEvent):
            stack.pop()
            yield ("]",)
            if stack and stack[-1] == "o":
                expect_key = True
        elif isinstance(ev, (yaml.ScalarEvent, yaml.AliasEvent)):
            if isinstance(ev, yaml.AliasEvent):
                kind, text = "alias", "*" + (ev.anchor or "")
            else:
                text = ev.value
                if ev.style:                      # quoted/block: a string
                    kind = "str"
                elif text in ("", "~", "null", "Null", "NULL"):
                    kind = "null"
                elif text in ("true", "false", "True", "False"):
                    kind = "bool"
                elif _YAML_INT.match(text):
                    kind = "int"
                elif _YAML_FLOAT.match(text):
                    kind = "float"
                else:
                    kind = "str"
            if stack and stack[-1] == "o" and expect_key:
                yield ("key", text)
                expect_key = False
            else:
                yield ("scalar", kind, text)
                if stack and stack[-1] == "o":
                    expect_key = True


# ----------------------------------------------------------- schema driver

def _node():
    return {"count": 0, "types": {}, "objs": 0, "keys": {}, "order": [],
            "elem": None, "arrays": 0, "alen_min": None, "alen_max": None,
            "sampled": False, "examples": []}


def _merge_scalar(node, kind, text):
    node["count"] += 1
    node["types"][kind] = node["types"].get(kind, 0) + 1
    if kind == "str":
        example = '"%s"' % (text[:EXAMPLE_CAP]
                            + ("…" if len(text) > EXAMPLE_CAP else ""))
    elif kind in ("int", "float", "datetime"):
        example = text
    else:
        return
    if example not in node["examples"] \
            and len(node["examples"]) < EXAMPLES_PER_NODE:
        node["examples"].append(example)


class Shape:
    """Streams events into a merged schema, honoring --sample and --path."""

    def __init__(self, sample, target=None):
        self.root = _node()
        self.sample = sample
        self.target = target      # parsed --path segments, or None
        self.hits = 1 if target is None else 0
        self.cstack = []
        self._comp = None

    def _start_value(self):
        st = self.cstack
        if st:
            top = st[-1]
            if top["kind"] == "o":
                comp = ("k", top.get("key") or "")
            else:
                comp = ("i", top["idx"])
                top["idx"] += 1
        else:
            comp = None
        self._comp = comp
        if st and st[-1]["node"] is not None:
            top = st[-1]
            node = top["node"]
            if top["kind"] == "o":
                child = node["keys"].get(comp[1])
                if child is None:
                    child = _node()
                    node["keys"][comp[1]] = child
                    node["order"].append(comp[1])
                return child
            if comp[1] < self.sample:
                if node["elem"] is None:
                    node["elem"] = _node()
                return node["elem"]
            return None                       # beyond --sample: count only
        if self.target is not None:
            path = [f["comp"] for f in st if f["comp"] is not None]
            if comp is not None:
                path.append(comp)
            if path == self.target:
                self.hits += 1
                return self.root
            return None
        return self.root if not st else None  # inside a skipped subtree

    def feed(self, events):
        for ev in events:
            tag = ev[0]
            if tag == "key":
                self.cstack[-1]["key"] = ev[1]
            elif tag == "scalar":
                node = self._start_value()
                if node is not None:
                    _merge_scalar(node, ev[1], ev[2])
            elif tag == "{":
                node = self._start_value()
                if node is not None:
                    node["count"] += 1
                    node["types"]["object"] = \
                        node["types"].get("object", 0) + 1
                    node["objs"] += 1
                self.cstack.append({"kind": "o", "node": node, "idx": 0,
                                    "key": None, "comp": self._comp})
            elif tag == "[":
                node = self._start_value()
                if node is not None:
                    node["count"] += 1
                    node["types"]["array"] = \
                        node["types"].get("array", 0) + 1
                    node["arrays"] += 1
                self.cstack.append({"kind": "a", "node": node, "idx": 0,
                                    "key": None, "comp": self._comp})
            elif tag == "}":
                self.cstack.pop()
            elif tag == "]":
                frame = self.cstack.pop()
                node = frame["node"]
                if node is not None:
                    length = frame["idx"]
                    node["alen_min"] = (length if node["alen_min"] is None
                                        else min(node["alen_min"], length))
                    node["alen_max"] = max(length, node["alen_max"] or 0)
                    if length > self.sample:
                        node["sampled"] = True


def render_schema(shape, level, key_cap=0):
    # level 0: full; 1: no examples; 2: depth<=2, no percentages;
    # 3: top-level keys only
    # key_cap (0 = unlimited) additionally limits siblings listed per node.
    # Depth levels alone bottom out at one line per top-level key, which is
    # unbounded for a wide record - a 4000-key object ignored every budget
    # because the ladder had no rung left to climb down to.
    out = []
    max_depth = {0: 99, 1: 99, 2: 2, 3: 1}[level]

    def emit(name, node, parent_objs, depth):
        types = "|".join(sorted(node["types"],
                                key=lambda t: (-node["types"][t], t)))
        parts = ["%s: %s" % (name, types or "empty")]
        if name == "root" and node["count"] > 1:
            parts[0] += " ×%d" % node["count"]
        if parent_objs and level < 2:
            parts.append("%d%%" % round(100.0 * node["count"] / parent_objs))
        if node["arrays"] and level < 3:
            lo, hi = node["alen_min"], node["alen_max"]
            parts.append("len %d" % hi if lo == hi else "len %d..%d"
                         % (lo, hi))
            if node["sampled"]:
                parts.append("(first %d sampled ~)" % shape.sample)
        if level == 0 and node["examples"]:
            parts.append("e.g. " + ", ".join(node["examples"]))
        out.append("  " * depth + "  ".join(parts))
        kids = [(k, node["keys"][k]) for k in node["order"]]
        if node["elem"] is not None:
            kids.append(("items", node["elem"]))
        if depth < max_depth:
            shown, hidden = kids, 0
            if key_cap and len(kids) > key_cap:
                shown, hidden = kids[:key_cap], len(kids) - key_cap
            for key, child in shown:
                emit(key, child, node["objs"], depth + 1)
            if hidden:
                out.append("  " * (depth + 1) + "… (+%d more key%s)"
                           % (hidden, "" if hidden == 1 else "s"))
        elif kids and level < 3:
            out.append("  " * (depth + 1) + "… (%d nested key%s)"
                       % (len(kids), "" if len(kids) == 1 else "s"))

    emit("root", shape.root, None, 0)
    if level >= 2:
        out.append("(collapsed for --max-tokens)")
    return out


# -------------------------------------------------------------------- csv

_INT_RX = re.compile(r"^[+-]?\d+$")
_FLOAT_RX = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _cell_kind(cell):
    if cell == "":
        return "null"
    c = cell.strip()
    if _INT_RX.match(c):
        return "int"
    if _FLOAT_RX.match(c) and any(x in c for x in ".eE"):
        return "float"
    if c.lower() in ("true", "false"):
        return "bool"
    if _DATE_RX.match(c):
        return "date"
    return "str"


def summarize_csv(fh, delim):
    reader = csv.reader(fh, delimiter=delim)
    header = next(reader, None)
    if not header:
        raise StructoError("empty file")
    cols = [{"name": h, "types": {}, "nulls": 0, "num_min": None,
             "num_max": None, "str_min": None, "str_max": None,
             "distinct": set(), "over": False} for h in header]
    rows = 0
    samples = []
    for row in reader:
        if not row:
            continue
        rows += 1
        if len(samples) < SAMPLE_ROWS:
            samples.append(row)
        for i, col in enumerate(cols):
            cell = row[i] if i < len(row) else ""
            kind = _cell_kind(cell)
            col["types"][kind] = col["types"].get(kind, 0) + 1
            if kind == "null":
                col["nulls"] += 1
                continue
            if kind in ("int", "float"):
                v = float(cell)
                col["num_min"] = (v if col["num_min"] is None
                                  else min(col["num_min"], v))
                col["num_max"] = (v if col["num_max"] is None
                                  else max(col["num_max"], v))
            elif kind == "bool":
                pass                        # min/max on booleans is noise
            else:
                col["str_min"] = (cell if col["str_min"] is None
                                  else min(col["str_min"], cell))
                col["str_max"] = (cell if col["str_max"] is None
                                  else max(col["str_max"], cell))
            if not col["over"]:
                col["distinct"].add(cell)
                if len(col["distinct"]) > DISTINCT_CAP:
                    col["over"] = True
                    col["distinct"] = set()
    return {"cols": cols, "rows": rows, "samples": samples,
            "delim": delim}


def _col_type(col):
    kinds = {k: n for k, n in col["types"].items() if k != "null"}
    if not kinds:
        return "null"
    ranked = sorted(kinds, key=lambda k: (-kinds[k], k))
    if len(ranked) == 1:
        return ranked[0]
    if set(ranked) == {"int", "float"}:
        return "float"
    return "mixed(%s)" % "|".join(ranked)


def _num(v):
    return ("%g" % v) if v is not None else "-"


def _straw(v, cap=12):
    if v is None:
        return "-"
    return '"%s"' % (v[:cap] + ("…" if len(v) > cap else ""))


def render_csv(model, level):
    # level 0: full + sample rows; 1: no sample rows; 2: type+null only;
    # 3: column names + row count
    cols, rows = model["cols"], model["rows"]
    if level >= 3:
        return ["columns (%d): %s" % (len(cols),
                                      ", ".join(c["name"] for c in cols)),
                "rows %d" % rows]
    out = ["columns (%d), rows %d:" % (len(cols), rows)]
    width = max(len(c["name"]) for c in cols)
    for col in cols:
        kind = _col_type(col)
        null_pct = round(100.0 * col["nulls"] / rows) if rows else 0
        line = "  %-*s  %-6s null %d%%" % (width, col["name"], kind,
                                           null_pct)
        if level < 2:
            if col["num_min"] is not None:
                line += "  min %s max %s" % (_num(col["num_min"]),
                                             _num(col["num_max"]))
            elif col["str_min"] is not None:
                line += "  min %s max %s" % (_straw(col["str_min"]),
                                             _straw(col["str_max"]))
            line += ("  distinct >%d ~" % DISTINCT_CAP if col["over"]
                     else "  distinct %d" % len(col["distinct"]))
        out.append(line)
    if level == 0 and model["samples"]:
        out.append("sample rows (%d):" % len(model["samples"]))
        for row in model["samples"]:
            out.append("  " + model["delim"].join(row))
    if level >= 2:
        out.append("(detail collapsed for --max-tokens)")
    return out


# -------------------------------------------------------------------- log

_TS_FORMATS = (
    ("iso-8601", re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
                            r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")),
    ("syslog", re.compile(r"^[A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2}")),
    ("clf", re.compile(r"\[\d{2}/[A-Z][a-z]{2}/\d{4}(?::\d{2}){3}")),
    ("epoch", re.compile(r"^\d{10}(?:\.\d+)?\b")),
)
_UUID_RX = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                      r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX_RX = re.compile(r"\b[0-9a-f]{8,}\b")
_NUM_RX = re.compile(r"\b\d+(?:\.\d+)?\b")
_QUOTED_RX = re.compile(r"\"[^\"]*\"|'[^']*'")


def _template(line, ts_rx):
    text = line
    if ts_rx is not None:
        text = ts_rx.sub("", text, count=1)
    text = _UUID_RX.sub("<uuid>", text)
    text = _HEX_RX.sub("<hex>", text)
    text = _QUOTED_RX.sub("<str>", text)
    text = _NUM_RX.sub("<n>", text)
    return " ".join(text.split())


def summarize_log(fh, path):
    count = 0
    first = last = None
    ts_name, ts_rx = None, None
    templates = {}
    overflow = 0
    for line in fh:
        count += 1
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        if first is None:
            first = (count, line)
            for name, rx in _TS_FORMATS:
                if rx.search(line):
                    ts_name, ts_rx = name, rx
                    break
        last = (count, line)
        tpl = _template(line, ts_rx)
        if tpl in templates:
            templates[tpl] += 1
        elif len(templates) < TEMPLATE_CAP:
            templates[tpl] = 1
        else:
            overflow += 1
    return {"path": path, "lines": count, "first": first, "last": last,
            "ts": ts_name, "templates": templates, "overflow": overflow}


def render_log(model, level):
    # level 0: top 5 + first/last; 1: top 3, no first/last; 2: counts only
    out = ["lines %d, timestamp %s" % (model["lines"],
                                       model["ts"] or "none detected")]
    ranked = sorted(model["templates"].items(),
                    key=lambda kv: (-kv[1], kv[0]))
    total = len(ranked) + (1 if model["overflow"] else 0)
    if level >= 2:
        out.append("templates: %d distinct%s"
                   % (total, " ~" if model["overflow"] else ""))
        out.append("(detail collapsed for --max-tokens)")
        return out
    top = TOP_TEMPLATES if level == 0 else 3
    out.append("templates (top %d of %d):" % (min(top, total), total))
    for tpl, n in ranked[:top]:
        out.append("  %d× %s" % (n, tpl[:120]))
    if model["overflow"]:
        out.append("  (+%d lines in templates beyond the %d-template cap ~)"
                   % (model["overflow"], TEMPLATE_CAP))
    if level == 0 and model["first"]:
        out.append("first %s:%d  %s" % (model["path"], model["first"][0],
                                        model["first"][1][:100]))
        out.append("last  %s:%d  %s" % (model["path"], model["last"][0],
                                        model["last"][1][:100]))
    return out


# -------------------------------------------------------------------- xml

def summarize_xml(path):
    from xml.etree.ElementTree import iterparse
    root = {"count": 0, "attrs": {}, "kids": {}, "korder": [], "text": 0}
    stack = [root]
    try:
        for event, elem in iterparse(path, events=("start", "end")):
            tag = elem.tag
            if event == "start":
                parent = stack[-1]
                node = parent["kids"].get(tag)
                if node is None:
                    node = {"count": 0, "attrs": {}, "kids": {},
                            "korder": [], "text": 0}
                    parent["kids"][tag] = node
                    parent["korder"].append(tag)
                node["count"] += 1
                for attr in elem.attrib:
                    node["attrs"][attr] = node["attrs"].get(attr, 0) + 1
                stack.append(node)
            else:
                node = stack.pop()
                if elem.text and elem.text.strip():
                    node["text"] += 1
                elem.clear()
    except SyntaxError as exc:
        raise StructoError("xml parse error: %s" % exc)
    return root


def render_xml(model, level):
    # level 0: full depth; 1: depth 2; 2: depth 1 + note
    max_depth = {0: 99, 1: 2, 2: 1}[level]
    out = []

    def emit(tag, node, depth):
        parts = ["%s ×%d" % (tag, node["count"])]
        attrs = sorted(node["attrs"].items(), key=lambda kv: (-kv[1], kv[0]))
        if attrs:
            parts.append(" ".join("@%s ×%d" % (a, n) for a, n in attrs))
        if node["text"]:
            parts.append("text ×%d" % node["text"])
        out.append("  " * (depth - 1) + "  ".join(parts))
        if depth < max_depth:
            for kid in node["korder"]:
                emit(kid, node["kids"][kid], depth + 1)
        elif node["korder"]:
            out.append("  " * depth + "… (%d nested element%s)"
                       % (len(node["korder"]),
                          "" if len(node["korder"]) == 1 else "s"))

    for tag in model["korder"]:
        emit(tag, model["kids"][tag], 1)
    if level >= 2:
        out.append("(nesting collapsed for --max-tokens)")
    return out


# -------------------------------------------------------------- detection

_TOML_TABLE = re.compile(r"^\[\[?[A-Za-z0-9_.\"'-]+\]\]?\s*(#.*)?$")
# The RHS must look like a TOML value, so `.env`-style `FOO=bar` (invalid
# TOML, and better summarized as a log) is not claimed here.
_TOML_KV = re.compile(r"^[A-Za-z0-9_.\"'-]+\s*=\s*"
                      r"([\"'\[{+-]|\d|true\b|false\b)")


def _looks_toml(lines):
    """TOML on the first meaningful line, or not at all.

    A TOML file opens with a table header (`[project]`, `[[a.b]]`) or a
    `key = value`; JSON opens with a bare `{`/`[` or a bracket holding
    commas, neither of which matches. Deciding on the first line only is
    what keeps this from claiming JSON documents: `[project]` used to sniff
    as JSON and come back as character soup (docs/known-issues)."""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        return bool(_TOML_TABLE.match(s) or _TOML_KV.match(s))
    return False


def detect(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in EXT_FORMATS:
        return EXT_FORMATS[ext], "extension"
    with open(path, "rb") as fh:
        head = fh.read(8192)
    if b"\0" in head:
        raise StructoError("%s looks binary; no structure to report"
                           % path)
    text = head.decode(TEXT_ENCODING, "replace")
    stripped = text.lstrip()
    lines = [l for l in text.splitlines() if l.strip()]
    if stripped.startswith("<"):
        return "xml", "sniffed"
    if _looks_toml(lines):
        return "toml", "sniffed"
    if stripped[:1] in "{[":
        if len(lines) >= 2:
            try:
                json.loads(lines[0])
                json.loads(lines[1])
                return "jsonl", "sniffed"
            except ValueError:
                pass
        return "json", "sniffed"
    for delim, fmt in (("\t", "tsv"), (",", "csv")):
        counts = [l.count(delim) for l in lines[:5]]
        if len(counts) >= 2 and counts[0] > 0 and len(set(counts)) == 1:
            return fmt, "sniffed"
    if lines and (lines[0].startswith("---")
                  or re.match(r"^[\w.-]+:(?:\s|$)", lines[0])):
        return "yaml", "sniffed"
    return "log", "sniffed"


def parse_path(spec):
    segs = []
    pos = 0
    for m in re.finditer(r"([^.\[\]]+)|\[(-?\d+)\]|\.", spec):
        if m.start() != pos:
            break
        pos = m.end()
        if m.group(1):
            segs.append(("k", m.group(1)))
        elif m.group(2) is not None:
            segs.append(("i", int(m.group(2))))
    if pos != len(spec) or not segs:
        raise StructoError("bad --path %r (expected like a.b[0].c)" % spec)
    return segs


def check_negatives(segs, fmt):
    """A negative index is only answerable at the JSONL record position.

    There, the file is a stream of records and `[-1]` costs a ring buffer of
    the trailing |N|. Inside a document, arrays are walked as an event stream
    with no length known until the closing bracket, so `a.b[-1]` would mean
    buffering the array — which breaks the O(schema+samples) memory promise
    that is the reason structo streams at all. Refuse and say why rather than
    silently reporting the path as absent.
    """
    for i, (kind, want) in enumerate(segs):
        if kind != "i" or want >= 0:
            continue
        if i == 0 and fmt == "jsonl":
            continue
        raise StructoError(
            "negative index [%d] only selects a JSONL record, and only as "
            "the first segment (structo streams; an array inside a document "
            "has no known length until it ends)" % want)


# ---------------------------------------------------- raw value extraction

_MISSING = object()


def _scalar_value(kind, text):
    if kind == "int":
        try:
            return int(text)
        except ValueError:
            return text
    if kind == "float":
        try:
            return float(text)
        except ValueError:
            return text
    if kind == "bool":
        return text.lower() == "true"
    if kind == "null":
        return None
    return text


def _materialize(events, first):
    """Build the Python value whose first event is `first`."""
    if first[0] == "{":
        obj = {}
        for ev in events:
            if ev[0] == "}":
                break
            obj[ev[1]] = _materialize(
                events, next(events, ("scalar", "null", "null")))
        return obj
    if first[0] == "[":
        arr = []
        for ev in events:
            if ev[0] == "]":
                break
            arr.append(_materialize(events, ev))
        return arr
    return _scalar_value(first[1], first[2])


def _skip_value(events, first):
    if first[0] not in ("{", "["):
        return
    depth = 1
    for ev in events:
        if ev[0] in ("{", "["):
            depth += 1
        elif ev[0] in ("}", "]"):
            depth -= 1
            if not depth:
                return


def _extract(events, first, segs):
    if not segs:
        return _materialize(events, first)
    kind, want = segs[0]
    if first[0] == "{" and kind == "k":
        for ev in events:
            if ev[0] == "}":
                return _MISSING
            child = next(events, ("scalar", "null", "null"))
            if ev[1] == want:
                return _extract(events, child, segs[1:])
            _skip_value(events, child)
    elif first[0] == "[" and kind == "i":
        idx = 0
        for ev in events:
            if ev[0] == "]":
                return _MISSING
            if idx == want:
                return _extract(events, ev, segs[1:])
            _skip_value(events, ev)
            idx += 1
    return _MISSING


def extract_value(events, segs):
    """Value at segs in an event stream — materializes only that subtree."""
    it = iter(events)
    for first in it:
        return _extract(it, first, segs)
    return _MISSING


def _walk(value, segs):
    for kind, want in segs:
        if kind == "k" and isinstance(value, dict) and want in value:
            value = value[want]
        elif kind == "i" and isinstance(value, list) \
                and 0 <= want < len(value):
            value = value[want]
        else:
            return _MISSING
    return value


def _nth_record(path, index):
    """Record `index` of a JSONL file, streaming; unparsable lines are not
    records (matching the summary's record count).

    Negative indices count from the end (`-1` is the last record), which is
    the common case for append-only logs where the record count isn't known
    up front. It stays streaming: only the trailing |index| records are held,
    so memory is O(|index|) rather than O(file).

    Returns (record, index) or (_MISSING, total records) if out of range."""
    seen = 0
    tail = collections.deque(maxlen=-index) if index < 0 else None
    with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if tail is not None:
                tail.append(record)
            elif seen == index:
                return record, seen
            seen += 1
    if tail is not None and len(tail) == -index:
        return tail[0], seen + index
    return _MISSING, seen


# ---------------------------------------------------- --select projection

def parse_select(spec):
    """`a,b.c,d[0]` -> [(label, segs), ...], order and labels preserved."""
    fields = []
    for raw in spec.split(","):
        name = raw.strip()
        if not name:
            raise StructoError("empty field in --select %r" % spec)
        segs = parse_path(name)
        # --select addresses fields *within* each record, so no position here
        # is the JSONL record index — every negative is unanswerable.
        check_negatives(segs, None)
        fields.append((name, segs))
    return fields


_TSV_CLEAN = re.compile(r"[\t\r\n]")


def _cell(value):
    """One TSV cell: missing is empty, containers compact JSON, tabs and
    newlines inside strings become spaces so a row stays one row."""
    if value is _MISSING:
        return ""
    if isinstance(value, str):
        return _TSV_CLEAN.sub(" ", value)
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      default=str)
    return _TSV_CLEAN.sub(" ", text)


def _seek(events, first, segs):
    """Advance the stream to the value at segs; return its first event."""
    if not segs:
        return first
    kind, want = segs[0]
    if first[0] == "{" and kind == "k":
        for ev in events:
            if ev[0] == "}":
                return _MISSING
            child = next(events, ("scalar", "null", "null"))
            if ev[1] == want:
                return _seek(events, child, segs[1:])
            _skip_value(events, child)
    elif first[0] == "[" and kind == "i":
        idx = 0
        for ev in events:
            if ev[0] == "]":
                return _MISSING
            if idx == want:
                return _seek(events, ev, segs[1:])
            _skip_value(events, ev)
            idx += 1
    return _MISSING


def iter_records(path, fmt, segs):
    """Yield records one at a time — memory stays O(one record)."""
    if fmt == "jsonl":
        with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                yield record
    elif fmt in ("json", "yaml"):
        with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
            events = iter(json_events(fh, full=True) if fmt == "json"
                          else yaml_events(fh))
            first = next(events, _MISSING)
            if first is not _MISSING and segs:
                first = _seek(events, first, segs)
            if first is _MISSING:
                raise StructoError("--path not found in %s" % path)
            if first[0] != "[":
                raise StructoError(
                    "--select reads an array of records (%s is not an "
                    "array)" % ("--path" if segs else "the top level"))
            for ev in events:
                if ev[0] == "]":
                    return
                yield _materialize(events, ev)
    elif fmt == "toml":
        value = toml_value(path)
        if segs:
            value = _walk(value, segs)
            if value is _MISSING:
                raise StructoError("--path not found in %s" % path)
        if not isinstance(value, list):
            raise StructoError(
                "--select reads an array of records (%s is not an array of "
                "tables)" % ("--path" if segs else "the top level"))
        yield from value
    elif fmt in ("csv", "tsv"):
        with open(path, encoding=TEXT_ENCODING, errors="replace",
                  newline="") as fh:
            reader = csv.reader(fh, delimiter="\t" if fmt == "tsv" else ",")
            header = next(reader, None)
            if not header:
                raise StructoError("empty file")
            for row in reader:
                if not row:
                    continue
                yield {h: (row[i] if i < len(row) else "")
                       for i, h in enumerate(header)}
    else:
        raise StructoError("--select needs record-shaped data (json array, "
                           "jsonl, yaml sequence, toml array of tables, "
                           "csv, tsv; %s detected)" % fmt)


def select_rows(path, fmt, segs, fields):
    """Header line then one TSV row per record."""
    records = iter_records(path, fmt, segs)
    first = next(records, _MISSING)     # surface source errors before output
    yield "\t".join(name for name, _ in fields)
    if first is _MISSING:
        return
    for record in itertools.chain([first], records):
        yield "\t".join(_cell(_walk(record, field)) for _, field in fields)


def extract_raw(path, fmt, target):
    """Exact value at --path; fully parses only what it returns."""
    if fmt == "jsonl":
        if target[0][0] != "i":
            raise StructoError('--raw on jsonl needs a record index '
                               '(--path "[N]" or "[N].a.b")')
        record, seen = _nth_record(path, target[0][1])
        if record is _MISSING:
            raise StructoError("record [%d] not found (%s has %d records)"
                               % (target[0][1], path, seen))
        value = _walk(record, target[1:])
    elif fmt == "json":
        with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
            value = extract_value(json_events(fh, full=True), target)
    elif fmt == "toml":
        value = _walk(toml_value(path), target)
    else:
        with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
            value = extract_value(yaml_events(fh), target)
    if value is _MISSING:
        raise StructoError("--path not found in %s" % path)
    return value


# --------------------------------------------------------------------- CLI

def summarize(path, fmt, sample, target):
    """Build (model, levels) for a detected format."""
    if fmt in TREE_FORMATS:
        record_index = None
        if fmt == "jsonl" and target and target[0][0] == "i":
            record_index, target = target[0][1], target[1:] or None
        shape = Shape(sample, target)
        records = None
        if fmt == "json":
            with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
                shape.feed(json_events(fh))
        elif fmt == "yaml":
            with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
                shape.feed(yaml_events(fh))
        elif fmt == "toml":
            shape.feed(value_events(toml_value(path)))
        elif record_index is not None:
            record, seen = _nth_record(path, record_index)
            if record is _MISSING:
                raise StructoError("record [%d] not found (%s has %d "
                                   "records)" % (record_index, path, seen))
            resolved = seen
            shape.feed(value_events(record))
        else:
            records = 0
            bad = 0
            with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        bad += 1
                        continue
                    records += 1
                    shape.feed(value_events(record))
        if target is not None and shape.hits == 0:
            raise StructoError("--path not found in %s" % path)
        extra = ""
        if record_index is not None:
            # Resolve a negative index in the header: the caller asked for
            # [-1] precisely because they didn't know the count, so naming
            # the absolute record saves the second call that used to be the
            # only way to learn it.
            extra = (", record %d (%d)" % (record_index, resolved)
                     if record_index < 0 else ", record %d" % record_index)
        elif records is not None:
            extra = ", records %d" % records
            if bad:
                extra += ", %d unparsable line%s skipped" % (
                    bad, "" if bad == 1 else "s")
        levels = [lambda lv=lv: render_schema(shape, lv)
                  for lv in (0, 1, 2, 3)]
        # Rungs below "top-level keys only", for records too wide for the
        # depth ladder to bound. Ends at 5 keys, which still names the
        # shape rather than truncating it to nothing.
        levels += [lambda kc=kc: render_schema(shape, 3, key_cap=kc)
                   for kc in (100, 40, 15, 5)]
        return extra, levels
    if fmt in ("csv", "tsv"):
        with open(path, encoding=TEXT_ENCODING, errors="replace",
                  newline="") as fh:
            model = summarize_csv(fh, "\t" if fmt == "tsv" else ",")
        return "", [lambda lv=lv: render_csv(model, lv)
                    for lv in (0, 1, 2, 3)]
    if fmt == "xml":
        model = summarize_xml(path)
        return "", [lambda lv=lv: render_xml(model, lv) for lv in (0, 1, 2)]
    with open(path, encoding=TEXT_ENCODING, errors="replace") as fh:
        model = summarize_log(fh, path)
    return "", [lambda lv=lv: render_log(model, lv) for lv in (0, 1, 2)]


def _relax_stdout(newline=None):
    """Pin UTF-8 so echoed values survive a cp1252 console default, and never
    die on an unencodable byte; --select also pins \\n endings so the TSV pipes
    the same way on every platform."""
    try:
        if newline is None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        else:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                                   newline=newline)
    except (AttributeError, ValueError):
        pass


def main(argv=None):
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        prog="structo",
        description="print the schema and shape of a data file "
                    "instead of its content")
    parser.add_argument("file", metavar="FILE")
    parser.add_argument("--path", metavar="A.B[0].C",
                        help="zoom into a JSON/YAML/TOML subtree (a leading "
                             "[N] picks JSONL record N)")
    parser.add_argument("--raw", action="store_true",
                        help="print the exact value at --path instead of "
                             "a schema (strings verbatim, else JSON)")
    parser.add_argument("--select", metavar="F1,F2",
                        help="project fields out of every record as TSV, "
                             "one row per record (json array/jsonl/yaml "
                             "sequence/toml array of tables/csv/tsv), for "
                             "piping to awk/sort")
    parser.add_argument("--sample", type=int, metavar="N",
                        default=DEFAULT_SAMPLE,
                        help="array elements aggregated per array "
                             "(default %d)" % DEFAULT_SAMPLE)
    # None means "not specified", so the default can differ by mode below.
    parser.add_argument("--max-tokens", type=int, metavar="N", default=None,
                        help="cap output at roughly N tokens (bytes/4) "
                             "(default: %d for schema output, unbounded for "
                             "--select/--raw; 0 = unbounded)"
                             % DEFAULT_MAX_TOKENS)
    parser.add_argument("--version", action="version",
                        version="structo %s" % __version__)
    args = parser.parse_args(argv)

    try:
        if not os.path.isfile(args.file):
            raise StructoError("not a file: %s" % args.file)
        fmt, how = detect(args.file)
        if fmt == "toml" and how == "sniffed":
            # The first-line sniff also matches ini/conf files, which tomllib
            # rejects. A sniff is a guess, so back off to the generic log
            # summary rather than failing on a file we were only guessing
            # about; an explicit .toml still reports the parse error.
            try:
                toml_value(args.file)
            except StructoError:
                fmt = "log"
        target = None
        if args.path:
            if fmt not in TREE_FORMATS:
                raise StructoError("--path zooms into json/yaml/jsonl/toml "
                                   "(%s detected as %s)" % (args.file, fmt))
            target = parse_path(args.path)
            check_negatives(target, fmt)
        if args.max_tokens is None:
            # ADR-006: the schema digest is capped by default, but --select
            # and --raw feed other programs and refuse rather than truncate
            # (see below). Defaulting those to a budget would turn an
            # ordinary `structo --select ... | awk` into an error, so an
            # unset cap means unbounded there and only there.
            args.max_tokens = (0 if (args.select or args.raw)
                               else DEFAULT_MAX_TOKENS)
        budget = max(0, args.max_tokens)
        if args.select:
            if args.raw:
                raise StructoError("--select and --raw print different "
                                   "things; pick one")
            if fmt == "jsonl" and target is not None:
                raise StructoError(
                    "--select reads every jsonl line as a record; address "
                    'into each one with the field names (--select "a.b")')
            fields = parse_select(args.select)
            if budget:
                # Two passes rather than buffering: a projection that
                # silently dropped records would corrupt whatever the
                # caller sums downstream, so measure first, then refuse.
                size, rows = 0, -1
                for line in select_rows(args.file, fmt, target, fields):
                    size += len(line.encode("utf-8", "replace")) + 1
                    rows += 1
                if size // 4 > budget:
                    raise StructoError(
                        "%d rows are ~%d tokens (budget %d); --select never "
                        "drops records — pipe it to awk/sort rather than "
                        "reading it" % (rows, size // 4, budget))
            _relax_stdout(newline="\n")
            for line in select_rows(args.file, fmt, target, fields):
                print(line)
            return 0
        if args.raw:
            if target is None:
                raise StructoError("--raw needs --path")
            value = extract_raw(args.file, fmt, target)
            if isinstance(value, str):
                text = value
            elif isinstance(value, (datetime.date, datetime.time)):
                text = value.isoformat()   # a TOML date is a value, not JSON
            else:
                text = json.dumps(value, ensure_ascii=False, indent=2,
                                  default=str)
            if budget and _est(text.splitlines()) > budget:
                raise StructoError(
                    "value at %s is ~%d tokens (budget %d); --raw never "
                    "truncates — narrow the path or drop --max-tokens"
                    % (args.path, _est(text.splitlines()), budget))
            lines = [text]
        else:
            extra, levels = summarize(args.file, fmt, max(1, args.sample),
                                      target)
            header = "structo %s — format: %s (%s)%s" % (args.file, fmt,
                                                         how, extra)
            if target is not None:
                header += ", path %s" % args.path
            wrapped = [lambda lv=lv: [header, ""] + lv() for lv in levels]
            lines = fit(wrapped, budget)
    except StructoError as exc:
        print("structo: %s" % exc, file=sys.stderr)
        return 2

    _relax_stdout()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
