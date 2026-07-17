import os
import re

import xread

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    return os.path.join(FIX, name)


_LINECACHE = {}


def lineno(name, needle, nth=1):
    """1-indexed line of the nth occurrence of needle in a fixture."""
    path = fx(name)
    if path not in _LINECACHE:
        with open(path, encoding="utf-8") as fh:
            _LINECACHE[path] = fh.read().splitlines()
    hits = [i for i, l in enumerate(_LINECACHE[path], 1) if needle in l]
    return hits[nth - 1]


def run(argv, capsys):
    code = xread.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def header(name, start, end):
    return "== %s:%d-%d ==" % (fx(name), start, end)


def headers_in(out):
    return [l for l in out.splitlines()
            if l.startswith("== ") and l.endswith(" ==")]


# ------------------------------------------------------------- symbol mode

def test_symbol_top_level_python(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "hypot"], capsys)
    assert code == 0
    start = lineno("sample.py", "# Compute the hypotenuse")
    end = lineno("sample.py", "return math.sqrt")
    assert out.splitlines()[0] == header("sample.py", start, end)
    assert "def hypot(a, b):" in out
    assert "# Used by the query-mode tests." in out   # attached comment
    assert "def _cache" not in out


def test_symbol_nested_python_with_decorator_and_comment(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "Greeter.greet"], capsys)
    assert code == 0
    start = lineno("sample.py", "# The main entry point")
    end = lineno("sample.py", 'return "hola')
    assert out.splitlines()[0] == header("sample.py", start, end)
    assert "@_cache" in out
    assert "greet_async" not in out


def test_symbol_bare_name_resolves_when_unique(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "greet_async"], capsys)
    assert code == 0
    assert "async def greet_async" in out


def test_symbol_unknown_errors(capsys):
    code, out, err = run([fx("sample.py"), "--symbol", "nope"], capsys)
    assert code == 2
    assert out == ""
    assert "symbol not found: nope" in err


def test_symbol_ambiguous_lists_candidates(capsys):
    code, _, err = run([fx("sample.py"), fx("sample.ts"),
                        "--symbol", "greet"], capsys)
    assert code == 2
    assert "ambiguous symbol greet" in err
    assert "sample.py" in err and "sample.ts" in err


def test_symbol_exact_qualname_in_both_files(capsys):
    code, out, _ = run([fx("sample.py"), fx("sample.ts"),
                        "--symbol", "Greeter.greet"], capsys)
    assert code == 0
    assert len(headers_in(out)) == 2
    assert "def greet(self, name):" in out
    assert "greet(target: Greetable): string {" in out


def test_symbol_typescript_class(capsys):
    code, out, _ = run([fx("sample.ts"), "--symbol", "Greeter"], capsys)
    assert code == 0
    start = lineno("sample.ts", "export class Greeter")
    end = lineno("sample.ts", "}", 8)  # class-closing brace
    first = out.splitlines()[0]
    assert first.startswith("== %s:%d-" % (fx("sample.ts"), start))
    assert "constructor(language" in out
    assert "static default(): Greeter {" in out
    assert "export default function farewell" not in out


def test_symbol_typescript_arrow_const_and_interface(capsys):
    code, out, _ = run([fx("sample.ts"), "--symbol", "shout"], capsys)
    assert code == 0
    assert "export const shout = (text: string): string => {" in out
    assert out.strip().endswith("};")

    code, out, _ = run([fx("sample.ts"), "--symbol", "Greetable"], capsys)
    assert code == 0
    assert "export interface Greetable {" in out
    assert "greet(): string;" in out


def test_symbol_typescript_method_with_attached_comment(capsys):
    code, out, _ = run([fx("sample.ts"), "--symbol", "Greeter.greet"], capsys)
    assert code == 0
    start = lineno("sample.ts", "// The main entry point")
    end = lineno("sample.ts", "return `hola, ${target.name}`;") + 1
    assert out.splitlines()[0] == header("sample.ts", start, end)


def test_symbol_prisma_model_with_attached_comment(capsys):
    code, out, _ = run([fx("schema.prisma"), "--symbol", "Book"], capsys)
    assert code == 0
    start = lineno("schema.prisma", "// A book of scripture.")
    end = lineno("schema.prisma", "verses Verse[]") + 1
    assert out.splitlines()[0] == header("schema.prisma", start, end)
    assert "model Book {" in out
    assert "model Verse" not in out


def test_symbol_prisma_braces_in_strings_and_comments(capsys):
    # `@default("{}")` and a `//` inside a datasource URL string must not
    # derail the block scanner.
    code, out, _ = run([fx("schema.prisma"), "--symbol", "Verse"], capsys)
    assert code == 0
    assert 'text   String @default("{}")' in out
    assert out.strip().endswith("}")
    assert "enum Testament" not in out

    code, out, _ = run([fx("schema.prisma"), "--symbol", "db"], capsys)
    assert code == 0
    assert 'url      = env("DATABASE_URL")' in out


def test_symbol_prisma_enum_and_generator(capsys):
    code, out, _ = run([fx("schema.prisma"), "--symbol", "Testament"],
                       capsys)
    assert code == 0
    assert "OLD" in out and "NEW" in out

    code, out, _ = run([fx("schema.prisma"), "--symbol", "client"], capsys)
    assert code == 0
    assert 'provider = "prisma-client-js"' in out


def test_symbol_unsupported_filetype_errors(tmp_path, capsys):
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")
    code, _, err = run([str(target), "--symbol", "x"], capsys)
    assert code == 2
    assert "unsupported file type" in err


# ------------------------------------------------------- lines/scope mode

def test_lines_raw_range(capsys):
    code, out, _ = run([fx("sample.py"), "--lines", "10-12"], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == header("sample.py", 10, 12)
    assert len(lines) == 4  # header + exactly three lines


def test_lines_scope_expands_to_enclosing_function(capsys):
    mid = lineno("sample.py", 'if self.language == "en":')
    code, out, _ = run([fx("sample.py"), "--lines",
                        "%d-%d" % (mid, mid), "--scope"], capsys)
    assert code == 0
    start = lineno("sample.py", "# The main entry point")
    end = lineno("sample.py", 'return "hola')
    assert out.splitlines()[0] == header("sample.py", start, end)
    assert "def greet(self, name):" in out


def test_lines_outside_any_symbol_stays_raw(capsys):
    code, out, _ = run([fx("sample.py"), "--lines", "3-5", "--scope"], capsys)
    assert code == 0
    assert out.splitlines()[0] == header("sample.py", 3, 5)


def test_lines_past_eof_errors(capsys):
    code, _, err = run([fx("sample.py"), "--lines", "9000"], capsys)
    assert code == 2
    assert "past end of file" in err


# -------------------------------------------------------------- query mode

def test_query_top_block_first_and_deterministic(capsys):
    code, out1, _ = run([fx("big.py"), "--query", "needle alpha"], capsys)
    assert code == 0
    first = out1.splitlines()[0]
    start = lineno("big.py", "def block_17(x):")
    assert first.startswith("== %s:%d-" % (fx("big.py"), start))
    _, out2, _ = run([fx("big.py"), "--query", "needle alpha"], capsys)
    assert out1 == out2


def test_query_blocks_are_whole_functions(capsys):
    code, out, _ = run([fx("sample.py"), "--query", "greeting language",
                        "--top", "1"], capsys)
    assert code == 0
    body = out.splitlines()
    # the excerpt is one whole top-level block: header then a full class/def
    assert body[0].startswith("== %s:" % fx("sample.py"))
    m = re.match(r"^== .*:(\d+)-(\d+) ==$", body[0])
    assert len(body) == 1 + int(m.group(2)) - int(m.group(1)) + 1


def test_query_no_hits_prints_nothing(capsys):
    code, out, _ = run([fx("sample.py"), "--query", "zzzznohit"], capsys)
    assert code == 0
    assert out == ""


def test_query_markdown_blocks_tile_the_file():
    # known-issue xread-query-returns-whole-markdown-file: the H1 section
    # spans the whole doc; as a query block it must be clamped at the next
    # heading so blocks partition the file instead of nesting.
    path, lines, symbols = xread.load([fx("doc.md")])[0]
    spans = sorted((a, b) for _, _, a, b
                   in xread._query_blocks(0, path, lines, symbols))
    assert (1, len(lines)) not in spans   # no whole-file block
    assert (5, 15) in spans               # ## Install section, intact
    covered_to = 0
    for a, b in spans:                    # no gaps, no overlap
        assert a == covered_to + 1
        covered_to = b
    assert covered_to == len(lines)


def test_query_markdown_all_keywords_beat_repeated_one(capsys):
    # A section matching every query word must outrank both a section
    # repeating one common word and an intro matching only inside longer
    # words ("building" is not a hit for "build").
    code, out, _ = run([fx("rank.md"), "--query", "suggested build order",
                        "--top", "1"], capsys)
    assert code == 0
    start = lineno("rank.md", "## Suggested build order")
    assert headers_in(out) == [header("rank.md", start, 11)]


def test_query_markdown_returns_section_not_whole_file(capsys):
    code, out, _ = run([fx("doc.md"), "--query", "install"], capsys)
    assert code == 0
    assert "make install" in out          # the ## Install section is there
    heads = headers_in(out)
    assert header("doc.md", 1, 27) not in heads   # not the whole file
    assert "Nothing yet." not in out              # ## FAQ (no hits) is not


def test_query_markdown_pulls_in_short_fenced_sibling(capsys):
    # known-issue xread-query-misses-adjacent-code-block: the fenced
    # payload sits in a short "### Error" section right above the
    # "### Error Codes" section the keywords land in — the match must
    # extend back over it.
    code, out, _ = run([fx("api.md"),
                        "--query", "error envelope error codes NOT_FOUND",
                        "--top", "1"], capsys)
    assert code == 0
    start = lineno("api.md", "### Error")           # the sibling
    end = lineno("api.md", "### Success") - 1
    assert headers_in(out) == [header("api.md", start, end)]
    assert '"code": "STRING"' in out                # the fenced envelope


def test_query_markdown_prose_sibling_stays_out(capsys):
    # A preceding sibling without a fence is scored on its own merits,
    # never padded in (rank.md: ## Deployment above ## Suggested build
    # order) — see test_query_markdown_all_keywords_beat_repeated_one.
    code, out, _ = run([fx("rank.md"), "--query", "suggested build order",
                        "--top", "1"], capsys)
    assert code == 0
    assert "## Deployment" not in out


# ------------------------------------------------------ markdown mode

def test_headings_outline(capsys):
    code, out, _ = run([fx("doc.md"), "--headings"], capsys)
    assert code == 0
    got = out.splitlines()
    path = fx("doc.md")
    assert got == [
        "%s:%d  # Sample Doc" % (path, lineno("doc.md", "# Sample Doc")),
        "%s:%d  ## Install" % (path, lineno("doc.md", "## Install")),
        "%s:%d  ## Usage" % (path, lineno("doc.md", "## Usage")),
        "%s:%d  ### Advanced Usage"
        % (path, lineno("doc.md", "### Advanced Usage")),
        "%s:%d  ## FAQ" % (path, lineno("doc.md", "## FAQ")),
    ]
    assert "not a heading" not in out


def test_headings_rejects_non_markdown(capsys):
    code, _, err = run([fx("sample.py"), "--headings"], capsys)
    assert code == 2
    assert "markdown" in err


def test_markdown_section_extraction(capsys):
    code, out, _ = run([fx("doc.md"), "--symbol", "Usage"], capsys)
    assert code == 0
    start = lineno("doc.md", "## Usage")
    end = lineno("doc.md", "## FAQ") - 1
    assert out.splitlines()[0] == header("doc.md", start, end)
    assert "### Advanced Usage" in out     # subsection included
    assert "## FAQ" not in out


def test_markdown_fenced_hash_not_a_heading(capsys):
    code, out, _ = run([fx("doc.md"), "--symbol", "Install"], capsys)
    assert code == 0
    assert "# this is not a heading" in out  # body text, not a boundary


# ------------------------------------------------- merging and elision

def test_elision_marker_between_excerpts(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "hypot",
                        "--symbol", "farewell"], capsys)
    assert code == 0
    hypot_end = lineno("sample.py", "return math.sqrt")
    farewell_start = lineno("sample.py", "def farewell(name):")
    gap = farewell_start - hypot_end - 1
    assert "… %d lines elided …" % gap in out.splitlines()


def test_overlapping_regions_merge_without_duplication(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "Greeter",
                        "--symbol", "Greeter.greet"], capsys)
    assert code == 0
    assert len(headers_in(out)) == 1                  # one merged excerpt
    assert out.count("def greet(self, name):") == 1   # no duplicated lines
    assert "elided" not in out


def test_multi_file_groups_in_argument_order(capsys):
    code, out, _ = run([fx("sample.ts"), fx("sample.py"),
                        "--lines", "1-2"], capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == header("sample.ts", 1, 2)
    assert lines[3] == ""                             # blank between groups
    assert lines[4] == header("sample.py", 1, 2)


# ------------------------------------------------------------- token cap

def test_budget_drops_lowest_score_blocks_first(capsys):
    code, full, _ = run([fx("big.py"), "--query", "total", "--top", "5"],
                        capsys)
    assert len(headers_in(full)) == 5
    code, out, _ = run([fx("big.py"), "--query", "total", "--top", "5",
                        "--max-tokens", "150"], capsys)
    assert code == 0
    kept = len(headers_in(out))
    assert 1 <= kept < 5
    assert "(dropped for --max-tokens:" in out
    top_header = full.splitlines()[0]
    assert top_header in out                          # best block survives


def test_budget_trims_single_excerpt_at_blank_boundary(capsys):
    code, out, _ = run([fx("big.py"), "--symbol", "big_table",
                        "--max-tokens", "100"], capsys)
    assert code == 0
    lines = out.splitlines()
    m = re.match(r"^== .*:(\d+)-(\d+) ==$", lines[0])
    start, end = int(m.group(1)), int(m.group(2))
    orig_end = lineno("big.py", "return w40")
    assert end < orig_end
    assert any("more lines elided (--max-tokens)" in l for l in lines)
    # the cut is at a chunk boundary: the source line after `end` is blank
    with open(fx("big.py"), encoding="utf-8") as fh:
        src = fh.read().splitlines()
    assert src[end].strip() == ""
    # no mid-statement cut: every body line is a real source line
    assert lines[-2] == src[end - 1]


def test_budget_never_cuts_symbol_mid_body_when_it_fits(capsys):
    code, out, _ = run([fx("sample.py"), "--symbol", "hypot",
                        "--max-tokens", "1000"], capsys)
    assert code == 0
    assert "return math.sqrt(a * a + b * b)" in out
    assert "elided" not in out
