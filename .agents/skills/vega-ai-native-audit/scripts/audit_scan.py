#!/usr/bin/env python3
"""FDE entry diagnosis: deterministic scan of what blocks the standard agent
flow (onboarding, planning, implementation, verification, review,
external integration, safe operation, skill-ification).
Items that need human/agent judgment are returned as UNKNOWN.
Output: JSON (items, gates, work_plan, handoff) + human summary (Japanese).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv",
             "__pycache__", "target", "out", "generated", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "coverage", ".idea", ".vscode",
             "apm_modules"}
# Installed agent skills (including this harness and its bundled runtime) are
# tooling, not the customer's project: scanning them would count e.g. the
# harness's own requirements.txt or scripts/ as project evidence.
SKIP_REL_DIRS = {".agents/skills", ".opencode/skills", ".opencode/skill", ".claude/skills"}
DOC_EXTS = {".md", ".rst"}

FLOWS = {"onboarding": "オンボーディング", "planning": "計画", "implementation": "実装",
         "verification": "検証", "review": "レビュー", "external-integration": "外部連携",
         "safe-operation": "安全運用", "skill-ification": "skill化"}
LAYER_NAMES = {"gate": "着手ゲート", "workflow": "継続ワークフロー", "safety": "安全運用"}
ITEM_META = {
    "repository-access": ("onboarding", "コードの取得/プッシュができず着手が止まる"),
    "issue-tracker-access": ("planning", "issue/MRの読み書きができず計画が手動になる"),
    "external-system-access": ("external-integration", "外部依存タスクで止まる（MCP/CLI/scriptの経路が必要）"),
    "ci-visibility": ("verification", "検証がローカルのみで壊れた変更が混入しやすい"),
    "environment-reproducibility": ("verification", "環境が再現できず検証ループが回らない"),
    "verification-commands": ("verification", "lint/typecheck/testを自走できず正しさを確認できない"),
    "test-assets": ("verification", "テストが無く、変更が壊したことを自律検出できない"),
    "dev-env-provisioning": ("onboarding", "環境構築が属人化して着手・環境再現が止まる"),
    "agent-docs": ("onboarding", "規約・コマンドを都度質問され自走できない"),
    "review-criteria": ("review", "レビュー基準・テンプレがなく自己レビューと顧客フローに乗らない"),
    "context-docs": ("onboarding", "背景を補えず誤った実装をする"),
    "test-isolation": ("verification", "外部API依存でテストがエアギャップで全滅・flakyになりループが止まる"),
    "skill-candidates": ("skill-ification", "属人手順がskill化されず都度人間が必要"),
    "secret-hygiene": ("safe-operation", "秘密情報がコンテキストに露出する"),
    "agent-permissions": ("safe-operation", "実行可否の境界が不明で危険操作を抑止できない"),
}

CI_PATHS = [".gitlab-ci.yml", ".github/workflows", "Jenkinsfile", "azure-pipelines.yml",
            "bitbucket-pipelines.yml", ".circleci/config.yml", "cloudbuild.yaml"]
LEGACY_CI = [".travis.yml", "appveyor.yml"]
LOCKFILE_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
                      "bun.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "Cargo.lock",
                      "go.sum", "Gemfile.lock", "composer.lock", "packages.lock.json",
                      "mix.lock", "Podfile.lock", "pdm.lock", "requirements.lock"}
VERSION_PIN_BASENAMES = {".nvmrc", ".node-version", ".python-version", ".ruby-version",
                         ".tool-versions", "mise.toml", ".mise.toml", "flake.nix",
                         "shell.nix", "default.nix", "devcontainer.json"}
MANIFEST_BASENAMES = {"package.json", "pyproject.toml", "requirements.txt", "Cargo.toml",
                      "go.mod", "Gemfile", "composer.json", "setup.py", "Pipfile",
                      "build.gradle", "pom.xml"}
TASK_RUNNERS = ["Makefile", "makefile", "justfile", "Justfile", "Taskfile.yml",
                "Taskfile.yaml", "run.py", "Rakefile", "noxfile.py", "tox.ini",
                "pytest.ini", ".pre-commit-config.yaml"]
MANIFEST_SCRIPT_KEYS = ("test", "lint", "typecheck", "check", "fmt", "format")
PYPROJECT_TEST_SECTIONS = ("[tool.pytest", "[tool.tox", "[tool.hatch.env", "[tool.nox",
                           "[tool.poe")
PYPROJECT_LINT_SECTIONS = ("[tool.ruff", "[tool.mypy", "[tool.flake8", "[tool.black", "[tool.isort")
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs"}
TEST_FILE_PATTERNS = [re.compile(r"(^test_|_test)\.py$"),
                      re.compile(r"(_test|\.test|\.spec|_spec)\.(js|jsx|ts|tsx|mjs|cjs)$"),
                      re.compile(r"_test\.go$"), re.compile(r"_test\.rs$"),
                      re.compile(r"(_test|_spec)\.rb$"), re.compile(r"Test\.java$"),
                      re.compile(r"Tests?\.cs$")]
TEST_CONFIG_BASENAMES = {"pytest.ini", "tox.ini", "conftest.py", "jest.config.js",
                         "jest.config.mjs", "jest.config.cjs", "jest.config.ts",
                         "vitest.config.ts", "vitest.config.mts", ".mocharc.yml",
                         ".mocharc.json", "karma.conf.js", "playwright.config.ts",
                         "playwright.config.js", "cypress.config.js", "cypress.config.ts"}
COMPOSE_BASENAMES = {"docker-compose.yml", "docker-compose.yaml", "compose.yml",
                     "compose.yaml", "devenv.nix"}
BOOTSTRAP_BASENAME_RE = re.compile(r"^(setup|bootstrap|install|init)\.(sh|py|rb)$")
BOOTSTRAP_SCRIPT_DIRS = ("scripts/", "bin/", "tools/", "dev/")
RUNNER_TARGET_RE = re.compile(r"^@?[a-zA-Z][\w-]*(setup|bootstrap|install|init)[\w-]*:", re.M)
MOCK_PATTERNS = [re.compile(r"unittest\.mock|from unittest import mock"),
                 re.compile(r"import responses|requests_mock"),
                 re.compile(r"import vcr|from vcr|httpretty"),
                 re.compile(r"\bnock\b"), re.compile(r"\bsinon\b"),
                 re.compile(r"jest\.mock|vi\.mock"), re.compile(r"\bmsw\b"),
                 re.compile(r"pytest-httpserver|wiremock|mock[-_]server|MockServer")]
EXTERNAL_URL_RE = re.compile(r"https?://[A-Za-z0-9.-]+")
INTERNAL_URL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org",
                      "example.net", "testserver", "jsonplaceholder", "github.com",
                      "raw.githubusercontent.com")
PROVISIONING_RUNNERS = ["Makefile", "makefile", "justfile", "Justfile", "Taskfile.yml",
                        "Taskfile.yaml", "run.py", "Rakefile"]
PROVISIONING_SKIP_SEGMENTS = ("example", "examples", "docs", "sample", "samples")
NETWORK_CALL_TOKENS = ("request(", "requests.", "fetch(", "urlopen", "httpx.",
                       "axios", "http.get", "http.post", "http.head", "http.delete",
                       "curl ", "wget ", "client.get(", "client.post(", "session.get(",
                       "session.post(", "aiohttp", "urllib")
COMMENT_LINE_PREFIXES = ("#", "//", "*", "/*", "<!--")
AGENT_DOCS_PRIMARY = ["AGENTS.md", "AGENT.md", ".opencode/AGENTS.md"]
AGENT_DOCS_SECONDARY = ["CLAUDE.md", ".claude/CLAUDE.md", "GEMINI.md",
                        ".github/copilot-instructions.md"]
REVIEW_DOCS = ["CONTRIBUTING.md", "docs/CONTRIBUTING.md", "docs/review.md",
               "docs/definition-of-done.md"]
TEMPLATE_PATHS = [".gitlab/merge_request_templates", ".gitlab/issue_templates",
                  ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE",
                  "ISSUE_TEMPLATE.md", ".commitlintrc.json", ".gitmessage"]
GLOSSARY_FILES = ["CONTEXT.md", "docs/glossary.md", "GLOSSARY.md"]
POLICY_FILES = ["opencode.json", "opencode.jsonc", ".claude/settings.json",
                "docs/agent-policy.md", "AGENT_POLICY.md"]
PROCEDURE_NAME_HINTS = ("deploy", "release", "runbook", "ops", "運用", "手順")
SECRET_PATTERNS = [r"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY", r"AKIA[0-9A-Z]{16}",
                   r"ghp_[A-Za-z0-9]{36}", r"glpat-[A-Za-z0-9_-]{20,}"]
KNOWN_EXAMPLES = ("AKIAIOSFODNN7EXAMPLE",)
FIXTURE_SEGMENTS = ("test", "tests", "example", "examples", "sample", "samples",
                    "fixture", "fixtures", "demo", "mock")
SECRET_KEY_RE = re.compile(r"(?i)(secret|token|password|passwd|credential|"
                           r"api[_-]?key|private[_-]?key|access[_-]?key|"
                           r"client[_-]?secret|auth)")
PLACEHOLDER_RE = re.compile(r"""(?xi)( \$\{ | <[^>]*> |
    ^your [_-] | ^example | ^changeme | ^xxx | ^dummy | ^placeholder |
    ^test | ^sample )""")

ITEMS = []
HANDOFF_SKILLS = []
HANDOFF_MCP = []
STATUS_ORDER = {"FAIL": 0, "PARTIAL": 1, "UNKNOWN": 2, "PASS": 3}
LAYER_ORDER = {"gate": 0, "workflow": 1, "safety": 2}


def add(item_id, layer, title, status, message, evidence=None, owner="FDE",
        effort="quick", action=None, skill_candidate=None, mcp_candidate=None):
    flow, impact = ITEM_META.get(item_id, ("", ""))
    ITEMS.append({"id": item_id, "layer": layer, "flow": flow,
                  "flow_name": FLOWS.get(flow, ""), "title": title, "impact": impact,
                  "status": status, "message": message,
                  "evidence": evidence or [], "owner": owner, "effort": effort,
                  "action": action or title})
    if skill_candidate:
        HANDOFF_SKILLS.append({"from": item_id, "candidate": skill_candidate})
    if mcp_candidate:
        HANDOFF_MCP.append({"from": item_id, "candidate": mcp_candidate})


def find_any(root, paths):
    return [rel for rel in paths if os.path.exists(os.path.join(root, rel))]


def prune_dirs(root, dirpath, dirnames):
    rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
    prefix = "" if rel_dir == "." else rel_dir + "/"
    dirnames[:] = [d for d in dirnames
                   if d not in SKIP_DIRS and prefix + d not in SKIP_REL_DIRS]


def iter_tree(root, max_files=50000):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        prune_dirs(root, dirpath, dirnames)
        for filename in filenames:
            count += 1
            if count > max_files:
                return
            # Normalize to "/" so checks like startswith("scripts/") and the
            # reported evidence paths behave the same on Windows.
            yield os.path.relpath(os.path.join(dirpath, filename), root).replace(os.sep, "/")


def iter_files(root, exts):
    for dirpath, dirnames, filenames in os.walk(root):
        prune_dirs(root, dirpath, dirnames)
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in exts:
                yield os.path.join(dirpath, filename)


def read_text(path, limit=100_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def run(cmd, cwd=None, timeout=20):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def is_dubious_ownership(stderr):
    """True if a git command failed only because of git's ownership guard
    (common when a repo is bind-mounted into a container/sandbox as a
    different user), not because the check it ran actually failed."""
    return "dubious ownership" in (stderr or "").lower()


def safe_directory_hint(root):
    return f"git config --global --add safe.directory {root}"


def is_fixture_path(rel):
    return any(seg in FIXTURE_SEGMENTS for seg in rel.lower().replace("\\", "/").split("/"))


# --- gates -----------------------------------------------------------------


def check_repository_access(root):
    title = "リポジトリアクセス"
    if not shutil.which("git"):
        add("repository-access", "gate", title, "UNKNOWN", "gitが導入されていない")
        return
    url, err = git_remote_url(root)
    if not url:
        if is_dubious_ownership(err):
            add("repository-access", "gate", title, "UNKNOWN",
                "gitが所有者不一致でコマンドを拒否している（診断環境側の設定要因。"
                "顧客リポジトリにリモートが無いとは限らない）",
                [err, safe_directory_hint(root)], owner="FDE",
                action=f"診断環境で `{safe_directory_hint(root)}` を実行して再診断する")
            return
        add("repository-access", "gate", title, "FAIL", "git remote origin がない",
            owner="顧客", action="リポジトリのリモートとアクセス権を確認する")
        return
    read_status, evidence = "UNKNOWN", []
    proc = run(["git", "-C", root, "ls-remote", "--exit-code", "origin", "HEAD"], timeout=25)
    if proc.returncode == 0:
        read_status, evidence = "PASS", ["git ls-remote: OK"]
    else:
        if "could not resolve" not in (proc.stderr or "").lower() and "timed out" not in (proc.stderr or "").lower():
            read_status = "FAIL"
        evidence.append(f"git ls-remote: {(proc.stderr or '').strip()[:120]}")
    write_status, write_evidence = check_write_access(root, url)
    label = {"PASS": "OK", "PARTIAL": "一部", "FAIL": "不可", "UNKNOWN": "未確認"}
    add("repository-access", "gate", title,
        min((read_status, write_status), key=lambda s: STATUS_ORDER[s]),
        f"読み取り={label[read_status]}、書き込み={label[write_status]}",
        evidence + write_evidence,
        owner="顧客", action="リモートの読み書き権限を確認する")


def git_remote_url(root):
    """Return (url, stderr). url is None on failure; stderr carries the
    reason so callers can distinguish "no remote configured" from
    "git refused to run" (e.g. dubious ownership)."""
    if not shutil.which("git"):
        return None, None
    proc = run(["git", "-C", root, "remote", "get-url", "origin"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip(), None
    return None, (proc.stderr or "").strip()


def remote_host(url):
    match = re.search(r"(?:@|//)([^/:]+)[/:]", url or "")
    return match.group(1) if match else None


def check_write_access(root, url):
    host = remote_host(url) or ""
    if "github" in host and shutil.which("gh"):
        proc = run(["gh", "repo", "view", "--json", "viewerPermission"], cwd=root)
        try:
            perm = json.loads(proc.stdout).get("viewerPermission", "") if proc.returncode == 0 else ""
        except json.JSONDecodeError:
            perm = ""
        if perm in ("ADMIN", "MAINTAIN", "WRITE"):
            return "PASS", [f"gh viewerPermission={perm}"]
        if perm:
            return "PARTIAL", [f"gh viewerPermission={perm}"]
    if "github" not in host and shutil.which("glab"):
        proc = run(["glab", "api", "projects/:id"], cwd=root)
        try:
            data = json.loads(proc.stdout) if proc.returncode == 0 else {}
        except json.JSONDecodeError:
            data = {}
        levels = [v.get("access_level") for v in (data.get("permissions") or {}).values()
                  if isinstance(v, dict) and v.get("access_level")]
        level = max(levels) if levels else None
        if level and level >= 30:
            return "PASS", [f"gitlab access_level={level}"]
        if level:
            return "PARTIAL", [f"gitlab access_level={level}"]
    return "UNKNOWN", ["書き込み権限は判定できず"]


def check_issue_tracker_access(root):
    title = "issue/MRトラッカーへのアクセス"
    url, _ = git_remote_url(root)
    if url and "github" in (remote_host(url) or ""):
        tool = "gh"
    elif url:
        tool = "glab"
    else:
        tool = "gh" if shutil.which("gh") else "glab"
    if not shutil.which(tool):
        add("issue-tracker-access", "gate", title, "FAIL", f"{tool} が導入されていない",
            action=f"{tool} を導入・認証して issue/MR を読み書きできるようにする")
        return
    proc = run([tool, "auth", "status"], timeout=30)
    authenticated = proc.returncode == 0
    if tool == "glab" and authenticated:
        authenticated = run(["glab", "api", "user"], timeout=30).returncode == 0
    add("issue-tracker-access", "gate", title, "PASS" if authenticated else "FAIL",
        f"{tool} が認証済み" if authenticated else f"{tool} が未認証",
        [f"{tool} auth: OK"] if authenticated else [proc.stderr.strip()[:200]],
        action=None if authenticated else f"{tool} をこのプロジェクトに対して認証する")


def find_mcp_servers(root):
    for rel in ("opencode.json", "opencode.jsonc", ".opencode/opencode.json"):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        text = read_text(path)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("mcp"), dict):
                return list(data["mcp"].keys())
        except json.JSONDecodeError:
            pass
        if re.search(r'"mcp"\s*:', text):
            return ["(未パースのmcpセクション)"]
    return []


def check_external_system_access(root):
    title = "外部システムへのアクセス"
    servers = find_mcp_servers(root)
    if servers:
        add("external-system-access", "gate", title, "PASS",
            f"外部アクセス設定あり（MCP: {', '.join(servers)}）",
            [f"mcp: {name}" for name in servers])
    else:
        add("external-system-access", "gate", title, "UNKNOWN",
            "MCP設定なし。必要な外部システムがあるか確認する",
            action="必要な外部システムを確定し、到達手段（MCP/CLI/script）を選ぶ",
            mcp_candidate="外部システム連携")


def check_ci_visibility(root):
    title = "CI状況の可視性"
    modern, legacy = find_any(root, CI_PATHS), find_any(root, LEGACY_CI)
    if modern:
        add("ci-visibility", "gate", title, "PASS", "CI設定あり", modern)
    elif legacy:
        add("ci-visibility", "gate", title, "PARTIAL",
            f"稼働していないレガシーCIのみ: {', '.join(legacy)}", legacy,
            owner="顧客", action="稼働中のCIへ移行する（GitHub Actions / GitLab CI 等）")
    else:
        add("ci-visibility", "gate", title, "PARTIAL",
            "CI設定なし（検証がローカルのみ）", owner="顧客",
            action="CIを導入し、リモート検証をエージェントが参照できるようにする")


def check_environment_reproducibility(root):
    title = "環境再現性"
    locks, pins, pinned_reqs, manifests = [], [], [], []
    for rel in iter_tree(root):
        base = os.path.basename(rel)
        if base in LOCKFILE_BASENAMES:
            locks.append(rel)
        elif base in VERSION_PIN_BASENAMES:
            pins.append(rel)
        elif re.match(r"(requirements|constraints)[^/]*\.txt$", base, re.IGNORECASE) \
                and "==" in read_text(os.path.join(root, rel), 200_000):
            pinned_reqs.append(rel)
        elif base in MANIFEST_BASENAMES:
            manifests.append(rel)
    evidence = sorted(set(locks + pins + pinned_reqs))[:5]
    if locks:
        add("environment-reproducibility", "gate", title, "PASS",
            f"lockfile: {len(locks)}、バージョンピン: {len(pins) + len(pinned_reqs)}",
            evidence, owner="顧客", action=None)
    elif pins or pinned_reqs:
        add("environment-reproducibility", "gate", title, "PARTIAL",
            f"lockfileなし。バージョンピンのみ: {len(pins) + len(pinned_reqs)}",
            evidence, owner="顧客", action="lockfileをコミットし、ランタイムのバージョンを固定する")
    elif manifests:
        add("environment-reproducibility", "gate", title, "FAIL",
            f"依存マニフェストはあるが、lockfile・ピンともにない: {len(manifests)}",
            manifests[:5], owner="顧客",
            action="lockfileをコミットし、ランタイムのバージョンを固定する")
    else:
        add("environment-reproducibility", "gate", title, "PARTIAL",
            "依存マニフェストなし（再現対象が存在しない）",
            owner="顧客", action="依存をバージョン固定で宣言する")


def check_verification_commands(root):
    title = "一発検証コマンド"
    runners, entries = find_any(root, TASK_RUNNERS), []
    pkg_path = os.path.join(root, "package.json")
    if os.path.exists(pkg_path):
        try:
            scripts = json.loads(read_text(pkg_path)).get("scripts", {})
        except (json.JSONDecodeError, AttributeError):
            scripts = {}
        found = [key for key in scripts if key in MANIFEST_SCRIPT_KEYS
                 or key.startswith("test")]
        if found:
            entries.append(f"package.json scripts: {', '.join(sorted(found)[:5])}")
    pyproject = read_text(os.path.join(root, "pyproject.toml")) \
        if os.path.exists(os.path.join(root, "pyproject.toml")) else ""
    if any(section in pyproject for section in PYPROJECT_TEST_SECTIONS):
        entries.append("pyproject.toml test設定")
    if os.path.exists(os.path.join(root, "setup.cfg")) \
            and "[tool:pytest]" in read_text(os.path.join(root, "setup.cfg")):
        entries.append("setup.cfg [tool:pytest]")
    if runners or entries:
        add("verification-commands", "gate", title, "PASS",
            "検証コマンドの手掛かりあり: " + ", ".join((runners + entries)[:5]),
            runners + entries, owner="顧客", action=None)
    elif any(section in pyproject for section in PYPROJECT_LINT_SECTIONS):
        add("verification-commands", "gate", title, "PARTIAL",
            "lint/typecheck設定はあるが、test実行が未定義", owner="顧客",
            action="test実行を1コマンドで定義し、AGENTS.md に記載する")
    else:
        add("verification-commands", "gate", title, "FAIL",
            "1コマンド検証の入口なし", owner="顧客",
            action="lint/typecheck/test を1コマンドで実行できるようにし、AGENTS.md に記載する")


_TEST_ASSET_CACHE = {}


def find_test_assets(root):
    if root not in _TEST_ASSET_CACHE:
        files, configs = [], []
        for rel in iter_tree(root):
            base = os.path.basename(rel)
            dirs = rel.replace("\\", "/").split("/")[:-1]
            if base in TEST_CONFIG_BASENAMES:
                configs.append(rel)
            elif any(d in TEST_DIR_NAMES for d in dirs):
                files.append(rel)
            elif any(p.search(base) for p in TEST_FILE_PATTERNS):
                files.append(rel)
        _TEST_ASSET_CACHE[root] = (files, configs)
    return _TEST_ASSET_CACHE[root]


def check_test_assets(root):
    title = "テスト資産の実在"
    files, configs = find_test_assets(root)
    if files:
        add("test-assets", "gate", title, "PASS",
            f"テスト資産あり: {len(files)}ファイル", sorted(files)[:3],
            owner="顧客", action=None)
    elif configs:
        add("test-assets", "gate", title, "PARTIAL",
            "テスト設定のみで、テスト本体が見つからない", sorted(configs)[:3],
            owner="顧客", action="最重要パスにテストを追加する")
    else:
        add("test-assets", "gate", title, "FAIL",
            "テスト資産なし。コードが壊れたことをエージェントが検出できない",
            owner="顧客", effort="structural",
            action="コアパスのテストを書く（最重要の1つからでよい）")


def check_dev_env_provisioning(root):
    title = "環境構築の1コマンド性"
    strong, dockerfiles = [], []

    def skip(rel):
        return any(seg in PROVISIONING_SKIP_SEGMENTS
                    for seg in rel.replace("\\", "/").split("/"))

    for rel in iter_tree(root):
        if skip(rel):
            continue
        base = os.path.basename(rel)
        if base in COMPOSE_BASENAMES or base == "devcontainer.json":
            strong.append(rel)
        elif base == "Dockerfile" or base.startswith("Dockerfile."):
            dockerfiles.append(rel)
        elif BOOTSTRAP_BASENAME_RE.match(base) and rel.startswith(BOOTSTRAP_SCRIPT_DIRS):
            strong.append(rel)
    for runner in find_any(root, PROVISIONING_RUNNERS):
        if RUNNER_TARGET_RE.search(read_text(os.path.join(root, runner))):
            strong.append(f"{runner}: setup/bootstrap系ターゲット")
    pkg_path = os.path.join(root, "package.json")
    if os.path.exists(pkg_path):
        try:
            scripts = json.loads(read_text(pkg_path)).get("scripts", {})
        except (json.JSONDecodeError, AttributeError):
            scripts = {}
        found = [key for key in scripts if key in ("setup", "bootstrap", "prepare", "install")]
        if found:
            strong.append(f"package.json scripts: {', '.join(found)}")
    if strong:
        add("dev-env-provisioning", "gate", title, "PASS",
            "環境構築の入口あり: " + ", ".join(sorted(set(strong))[:3]),
            sorted(set(strong))[:5], owner="顧客", action=None)
    elif dockerfiles:
        add("dev-env-provisioning", "gate", title, "PARTIAL",
            "イメージ定義のみで、起動・セットアップが1コマンドになっていない",
            sorted(set(dockerfiles))[:3], owner="顧客",
            action="起動までを1コマンド化する（compose化 等）")
    else:
        add("dev-env-provisioning", "gate", title, "FAIL",
            "環境構築の入口なし。手順が属人化している",
            owner="顧客", effort="structural",
            action="環境構築を1コマンド化する（compose / devcontainer / bootstrapスクリプト）")


def check_agent_docs(root):
    title = "エージェント知識の入口（AGENTS.md）"
    primary, secondary = find_any(root, AGENT_DOCS_PRIMARY), find_any(root, AGENT_DOCS_SECONDARY)
    if primary:
        size = os.path.getsize(os.path.join(root, primary[0]))
        add("agent-docs", "gate", title, "PASS" if size >= 100 else "PARTIAL",
            f"{primary[0]} あり（{size} bytes）" if size >= 100 else f"{primary[0]} がほぼ空",
            primary, action=None if size >= 100 else "AGENTS.md にコマンドと規約を書く")
    elif secondary:
        add("agent-docs", "gate", title, "PARTIAL",
            "標準的でないエージェント文書のみ存在", secondary,
            action="AGENTS.md を作る（既存の文書から移植）")
    else:
        add("agent-docs", "gate", title, "FAIL", "AGENTS.md なし",
            action="コマンド・規約・非コード知識を AGENTS.md に書く")


# --- workflow ---------------------------------------------------------------


def check_review_criteria(root):
    title = "レビュー基準とテンプレート"
    review, templates = find_any(root, REVIEW_DOCS), find_any(root, TEMPLATE_PATHS)
    add("review-criteria", "workflow", title,
        "PASS" if review else ("PARTIAL" if templates else "FAIL"),
        f"レビュー文書: {review or 'なし'}、テンプレ/コミット規約: {len(templates)}",
        (review + templates)[:5], owner="顧客",
        action=None if review else "レビュー基準（definition of done）を文書化し、issue/MRテンプレートを置く")


def check_context_docs(root):
    title = "文脈供給（用語集・ADR）"
    adr = os.path.isdir(os.path.join(root, "docs", "adr")) or os.path.isdir(os.path.join(root, "adr"))
    glossary = find_any(root, GLOSSARY_FILES)
    docs_dir = os.path.isdir(os.path.join(root, "docs"))
    status = "PASS" if (adr and glossary) else ("PARTIAL" if (docs_dir or adr or glossary) else "FAIL")
    add("context-docs", "workflow", title, status,
        f"ADR: {'あり' if adr else 'なし'}、用語集: {glossary or 'なし'}、docs/: {'あり' if docs_dir else 'なし'}",
        glossary, effort="structural",
        action=None if status == "PASS" else "docs を整備し、用語集とADRを置いて背景を供給する")


def is_internal_host(host):
    if host.endswith((".test", ".example", ".invalid")):
        return True
    return any(host == h or host.endswith("." + h) for h in INTERNAL_URL_HOSTS)


def check_test_isolation(root):
    title = "テストの独立性"
    files, _configs = find_test_assets(root)
    if not files:
        add("test-isolation", "workflow", title, "UNKNOWN",
            "テスト資産がないため評価外（test-assets を先に解消する）")
        return
    call_hits, literal_hits, mock_files = [], [], []
    for rel in files[:1500]:
        if len(call_hits) + len(literal_hits) >= 20:
            break
        text = read_text(os.path.join(root, rel), 200_000)
        if any(p.search(text) for p in MOCK_PATTERNS):
            mock_files.append(rel)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(COMMENT_LINE_PREFIXES):
                continue
            external = any(
                not is_internal_host(m.group(0).split("//", 1)[1].split("/")[0].lower())
                for m in EXTERNAL_URL_RE.finditer(line))
            if not external:
                continue
            hit = f"{rel}: {stripped[:80]}"
            if any(token in stripped for token in NETWORK_CALL_TOKENS):
                call_hits.append(hit)
            else:
                literal_hits.append(hit)
            if len(call_hits) + len(literal_hits) >= 20:
                break
    scanned = min(len(files), 1500)
    hits = call_hits + literal_hits
    if not hits:
        add("test-isolation", "workflow", title, "PASS",
            f"テストコードに外部URL参照なし（走査: {scanned}ファイル）",
            owner="顧客", action=None)
    elif call_hits and mock_files:
        add("test-isolation", "workflow", title, "PARTIAL",
            f"外部呼び出しの疑い（モック併用あり、実依存は要確認）: {len(call_hits)}件",
            (call_hits + mock_files[:1])[:5], owner="顧客", effort="structural",
            action="外部依存をモックへ寄せ、オフラインでテストが回るようにする")
    elif call_hits:
        add("test-isolation", "workflow", title, "FAIL",
            f"テストから外部URLへの直接呼び出しの疑い: {len(call_hits)}件",
            call_hits[:5], owner="顧客", effort="structural",
            action="外部依存をモックへ置換し、オフラインでテストが回るようにする")
    else:
        add("test-isolation", "workflow", title, "PARTIAL",
            f"外部URL参照あり（呼び出しの形跡なし。エアギャップ時に要確認）: {len(literal_hits)}件",
            literal_hits[:5], owner="顧客",
            action="外部URLの依存有無を確認し、必要ならモックへ置換する")


def check_skill_candidates(root):
    title = "手順のskill化候補"
    candidates = [rel for rel in iter_tree(root)
                  if rel.endswith(tuple(DOC_EXTS))
                  and any(h in os.path.basename(rel).lower() for h in PROCEDURE_NAME_HINTS)]
    if any(rel.startswith("scripts/") for rel in iter_tree(root)):
        candidates.append("scripts/")
    add("skill-candidates", "workflow", title, "UNKNOWN",
        f"手順書候補: {len(candidates)}", sorted(set(candidates))[:10],
        effort="structural", action="繰り返し手順をskill化する（skill-creator）",
        skill_candidate="docs/scripts 内の手順。skill化を検討する")


# --- safety -----------------------------------------------------------------


def git_secret_hits(root):
    """Return (hits, scan_errors). `git grep` exits 1 for "no match" (a
    normal, successful scan) but >=2 for real errors (bad pattern, I/O,
    ownership guard, ...) - those must not be silently folded into "no
    secrets found", or a failed scan looks identical to a clean one."""
    hits, scan_errors = {}, []
    for pattern in SECRET_PATTERNS:
        proc = run(["git", "-C", root, "grep", "-n", "-E", "-e", pattern, "--", "."], timeout=30)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                path, _, text = line.partition(":")
                if any(example in text for example in KNOWN_EXAMPLES):
                    continue
                hits.setdefault(path, []).append(text.strip()[:80])
        elif proc.returncode != 1:
            scan_errors.append((proc.stderr or f"git grep exited {proc.returncode}").strip()[:160])
    return hits, scan_errors


def env_secret_key(path):
    for line in read_text(path).splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("\"'")
        if len(value) >= 8 and SECRET_KEY_RE.search(key) and not PLACEHOLDER_RE.match(value):
            return key
    return None


def check_secret_hygiene(root):
    title = "秘密情報衛生"
    if not shutil.which("git"):
        add("secret-hygiene", "safety", title, "UNKNOWN",
            "gitが使えないため走査できない", action="gitチェックアウト上で再実行する")
        return
    proc = run(["git", "-C", root, "rev-parse", "--is-inside-work-tree"])
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        if is_dubious_ownership(proc.stderr):
            add("secret-hygiene", "safety", title, "UNKNOWN",
                "gitが所有者不一致で走査を拒否している（診断環境側の設定要因。"
                "秘密情報の有無は未確認のままFAIL/PASSを断定しない）",
                [(proc.stderr or "").strip()[:200], safe_directory_hint(root)],
                action=f"診断環境で `{safe_directory_hint(root)}` を実行して再走査する")
            return
        add("secret-hygiene", "safety", title, "UNKNOWN",
            "gitリポジトリとして認識できないため走査できない", action="gitチェックアウト上で再実行する")
        return
    hits, scan_errors = git_secret_hits(root)
    if scan_errors:
        add("secret-hygiene", "safety", title, "UNKNOWN",
            f"一部パターンの走査が失敗し、秘密情報の有無を断定できない: {len(scan_errors)}件",
            scan_errors[:5], action="走査エラーを解消して再実行する（git grepが失敗する環境要因を確認）")
        return
    production = {p: t for p, t in hits.items() if not is_fixture_path(p)}
    fixtures = {p: t for p, t in hits.items() if is_fixture_path(p)}
    if production:
        add("secret-hygiene", "safety", title, "FAIL",
            f"本番相当の秘密情報がコミットされている: {len(production)}ファイル",
            sorted(production)[:5], owner="顧客",
            action="即座にローテーションし、履歴から除去する")
        return
    proc = run(["git", "-C", root, "ls-files", ".env", "*.env", ".env.*"], timeout=15)
    tracked = [l for l in proc.stdout.splitlines()
               if l and not l.endswith((".example", ".sample", ".template"))] \
        if proc.returncode == 0 else []
    leaked = [rel for rel in tracked if env_secret_key(os.path.join(root, rel))]
    if leaked:
        add("secret-hygiene", "safety", title, "FAIL",
            f"秘密値を含む .env が追跡されている: {len(leaked)}",
            leaked[:5], owner="顧客", action="git管理から外し、値をローテーションする")
        return
    if fixtures:
        add("secret-hygiene", "safety", title, "PARTIAL",
            f"テスト用の鍵・サンプルがコミットされている: {len(fixtures)}ファイル",
            sorted(fixtures)[:5], owner="顧客",
            action="テスト用の鍵はコミットせず実行時に生成する")
        return
    if tracked:
        add("secret-hygiene", "safety", title, "PARTIAL",
            f".env類が追跡されているが、秘密値は検出されず: {len(tracked)}",
            tracked[:5], owner="顧客",
            action="実秘密は .env.example テンプレと分離し、git管理外に置く")
        return
    add("secret-hygiene", "safety", title, "PASS", "追跡ファイルに秘密情報は検出されず")


def check_agent_permissions(root):
    title = "エージェント権限ポリシー"
    found = find_any(root, POLICY_FILES)
    text_hit = [rel for rel in find_any(root, AGENT_DOCS_PRIMARY)
                if re.search(r"permission|権限", read_text(os.path.join(root, rel)).lower())]
    add("agent-permissions", "safety", title, "PASS" if (found or text_hit) else "FAIL",
        "権限ポリシーの設定・文書あり" if (found or text_hit)
        else "エージェントの権限ポリシーが未文書化", found + text_hit,
        action=None if (found or text_hit) else "エージェントに許す操作・範囲を文書化する")


CHECKS = [check_repository_access, check_issue_tracker_access,
          check_external_system_access, check_ci_visibility,
          check_environment_reproducibility, check_verification_commands,
          check_test_assets, check_dev_env_provisioning,
          check_agent_docs, check_review_criteria, check_context_docs,
          check_test_isolation, check_skill_candidates,
          check_secret_hygiene, check_agent_permissions]


def build_work_plan(items):
    actionable = sorted((i for i in items if i["status"] != "PASS"),
                        key=lambda i: (LAYER_ORDER[i["layer"]], STATUS_ORDER[i["status"]], i["id"]))
    return [{"order": n + 1, "id": i["id"], "flow": i["flow"], "flow_name": i["flow_name"],
             "title": i["title"], "impact": i["impact"], "action": i["action"],
             "owner": i["owner"], "effort": i["effort"], "status": i["status"]}
            for n, i in enumerate(actionable)]


def main():
    parser = argparse.ArgumentParser(
        description="FDE entry diagnosis: 標準のエージェント開発フローの阻害要因を決定論的に走査する。"
                    "着手ゲート・継続ワークフロー・安全運用の各項目を判定し、判断が必要な項目はUNKNOWNを返す。")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--out", help="write JSON report to file")
    parser.add_argument("--quiet", action="store_true", help="only print JSON")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 3
    for check in CHECKS:
        try:
            check(root)
        except Exception as exc:
            add("scanner-error", "gate", f"スキャナエラー（{check.__name__}）",
                "UNKNOWN", str(exc))

    work_plan = build_work_plan(ITEMS)
    report = {"root": root, "generated_at": datetime.now(timezone.utc).isoformat(),
              "gates": [i for i in ITEMS if i["layer"] == "gate"], "items": ITEMS,
              "work_plan": work_plan, "handoff": {"skills": HANDOFF_SKILLS, "mcp": HANDOFF_MCP}}

    if not args.quiet:
        for layer, name in LAYER_NAMES.items():
            print(f"== {name} ==")
            for i in (x for x in ITEMS if x["layer"] == layer):
                flow = f"｜{i['flow_name']}" if i["flow_name"] else ""
                print(f"[{i['status']:7}] {i['id']}（{i['title']}）{flow}: {i['message']}")
                for line in i["evidence"][:3]:
                    print(f"            - {line}")
        print("\n== 解除計画 ==")
        for step in work_plan:
            print(f"{step['order']:2}. [{step['status']}/{step['effort']}/{step['owner']}] "
                  f"{step['id']}: {step['action']}")
        if HANDOFF_SKILLS or HANDOFF_MCP:
            print("\n== handoff候補 ==")
            for entry in HANDOFF_SKILLS:
                print(f"  skill: {entry['candidate']}（from {entry['from']}）")
            for entry in HANDOFF_MCP:
                print(f"  mcp:   {entry['candidate']}（from {entry['from']}）")

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
    if args.quiet:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
