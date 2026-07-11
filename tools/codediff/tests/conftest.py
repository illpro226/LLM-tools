import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPOINDEX = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "repoindex", "repoindex.py"))

CORE_V1 = '''\
RETRY_COUNT = 3


def login(user):
    """Log a user in."""
    session = create_session(user)
    return session


def validate_token(token):
    # deprecated: use login() instead
    return token is not None
'''

CORE_V2 = '''\
RETRY_COUNT = 5


def login(user, mfa=None):
    """Log a user in."""
    session = create_session(user)
    if mfa is not None:
        verify_mfa(user, mfa)
    return session
'''

FMT_V1 = "def add(a,b):\n    return a+b\n"
FMT_V2 = "def add(a, b):\n    # sum of two numbers\n    return a + b\n"

APP_V1 = "import os\nimport sys\n\n\ndef run():\n" \
         "    return os.getcwd() + sys.prefix\n"
APP_V2 = "import sys\nimport os\n\n\ndef run():\n" \
         "    return os.getcwd() + sys.prefix\n"

SHAPES_V1 = "def area(w, h):\n    scale = 2\n    return w * h * scale\n"
SHAPES_V2 = "def compute_area(w, h):\n    scale = 2\n" \
            "    return w * h * scale\n"

CLIENT_V1 = "def fetch(url, timeout=30):\n    return get(url, timeout)\n"
CLIENT_V2 = "def fetch(url, timeout=60):\n    return get(url, timeout)\n"

WIDGET_V1 = "export function render(el) {\n  return el;\n}\n"
WIDGET_V2 = "export function render(el, opts) {\n  return el;\n}\n"

TEST_CORE = "from src.auth.core import login\n\n\n" \
            "def test_login():\n    assert login('u')\n"


def g(repo, *args):
    env = dict(os.environ,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
               GIT_COMMITTER_NAME="Test",
               GIT_COMMITTER_EMAIL="test@example.com")
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def write(repo, rel, content):
    path = os.path.join(str(repo), rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


@pytest.fixture(autouse=True)
def _isolated_git_env(monkeypatch):
    """codediff's own subprocess calls must not see host git config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def base_repo(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    g(work, "init", "-b", "main")
    write(work, "src/auth/core.py", CORE_V1)
    write(work, "src/fmt.py", FMT_V1)
    write(work, "src/app.py", APP_V1)
    write(work, "src/shapes.py", SHAPES_V1)
    write(work, "src/client.py", CLIENT_V1)
    write(work, "src/widget.js", WIDGET_V1)
    write(work, "tests/test_core.py", TEST_CORE)
    g(work, "add", "-A")
    g(work, "commit", "-m", "base")
    return work


def apply_changes(work):
    """The scripted working-tree edits every section test asserts on."""
    write(work, "src/auth/core.py", CORE_V2)   # API sig, const, behavior,
    write(work, "src/fmt.py", FMT_V2)          # ... removed deprecated
    write(work, "src/app.py", APP_V2)          # imports reshuffled
    write(work, "src/shapes.py", SHAPES_V2)    # symbol rename
    write(work, "src/client.py", CLIENT_V2)    # default value change
    write(work, "src/widget.js", WIDGET_V2)    # js signature change


@pytest.fixture()
def repo(tmp_path):
    """Base commit plus the scripted working-tree edits."""
    work = base_repo(tmp_path)
    apply_changes(work)
    return work


@pytest.fixture()
def indexed_repo(tmp_path):
    """Same repo with a .repoindex index built at the base commit."""
    work = base_repo(tmp_path)
    proc = subprocess.run([sys.executable, REPOINDEX, "--root", str(work),
                           "build"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    apply_changes(work)
    return work
