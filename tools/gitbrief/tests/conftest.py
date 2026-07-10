import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

A_V1 = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"
A_V2 = A_V1 + "\n\ndef gamma():\n    return 3\n"          # staged: +4 -0
A_V3 = A_V2.replace("return 1", "return 10")               # unstaged: +1 -1
B_V1 = "one\ntwo\nthree\n"
B_V2 = B_V1 + "four\n"                                     # unstaged: +1 -0
NOTES = "n1\nn2\nn3\n"                                     # untracked: +3


def g(repo, *args, name="Test", email="test@example.com"):
    env = dict(os.environ,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email,
               GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email)
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def write(repo, rel, content):
    path = os.path.join(str(repo), rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def commit_file(repo, rel, content, message, **who):
    write(repo, rel, content)
    g(repo, "add", rel)
    g(repo, "commit", "-m", message, **who)


@pytest.fixture(autouse=True)
def _isolated_git_env(monkeypatch):
    """gitbrief's own subprocess calls must not see host git config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture()
def repo(tmp_path):
    """Scripted repo: upstream drift, staged+unstaged+untracked, 7 commits."""
    work = tmp_path / "work"
    work.mkdir()
    g(work, "init", "-b", "main")
    commit_file(work, "a.py", A_V1, "add alpha and beta")          # c1
    commit_file(work, "b.txt", B_V1, "add b")                      # c2
    commit_file(work, "hist.txt", "h1\n", "start history")         # c3
    commit_file(work, "hist.txt", "h1\nh2\n", "fix parser bug",
                name="Alice", email="alice@example.com")           # c4
    commit_file(work, "hist.txt", "h1\nh2\nh3\n", "extend history")  # c5
    origin = tmp_path / "origin.git"
    g(tmp_path, "init", "--bare", str(origin))
    g(work, "remote", "add", "origin", str(origin))
    g(work, "push", "-u", "origin", "main")
    commit_file(work, "hist.txt", "h1\nh2\nh3\nh4\n", "will be behind")
    g(work, "push")
    g(work, "reset", "--hard", "HEAD~1")                # behind 1
    commit_file(work, "hist.txt", "h1\nh2\nh3\nx1\n", "ahead one")   # c7
    commit_file(work, "hist.txt", "h1\nh2\nh3\nx1\nx2\n", "ahead two")  # c8
    write(work, "a.py", A_V2)
    g(work, "add", "a.py")                              # staged  +4 -0
    write(work, "a.py", A_V3)                           # unstaged +1 -1
    write(work, "b.txt", B_V2)                          # unstaged +1 -0
    write(work, "notes.txt", NOTES)                     # untracked +3
    return work


TS_V1 = ("export function mount(el) {\n  return el;\n}\n\n"
         "export class View {\n  draw() {}\n}\n")
TS_V2 = TS_V1 + "\nexport const helper = (x) => x + 1;\n"
APY_V1 = ("def alpha():\n    return 1\n\n\n"
          "def legacy():\n    return 0\n\n\n"
          "def beta():\n    return 2\n")
APY_V2 = ("def alpha():\n    return 42\n\n\n"
          "def beta():\n    return 2\n\n\n"
          "def gamma():\n    return 3\n")


@pytest.fixture()
def pr_repo(tmp_path):
    """main + feature branch with known symbol-level edits."""
    work = tmp_path / "prwork"
    work.mkdir()
    g(work, "init", "-b", "main")
    commit_file(work, "a.py", APY_V1, "base python")
    commit_file(work, "web.ts", TS_V1, "base ts")
    g(work, "switch", "-c", "feature")
    commit_file(work, "a.py", APY_V2, "rework python symbols")
    commit_file(work, "web.ts", TS_V2, "add ts helper")
    commit_file(work, "data.csv", "x,y\n1,2\n", "add data")
    return work
