#!/usr/bin/env python3
"""Run trigger evaluation for a skill description on OpenCode.

Tests whether a skill's description causes the agent to trigger (load the
skill) for a set of queries. Outputs results as JSON.

Requires the `opencode` CLI. Runs use `--auto` so that eval queries do not
stall on permission prompts; only use eval sets you trust.
The skill under test should be absent from the project's skill directories
(.opencode/skills, .agents/skills): a same-name installed skill with a
different description can produce false positives (see detect_trigger).
"""

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Allow direct execution (`python <skill-dir>/scripts/<name>.py`) from any
# working directory: make the skill directory importable as the `scripts` package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import parse_skill_md

AGENT_CMD = os.environ.get("SKILL_EVAL_AGENT_CMD", "opencode")


PROJECT_MARKERS = (".agents", ".opencode", ".git")


def find_project_root(start: Path | None = None) -> Path:
    """Find the project the trigger evals run in.

    Walks up from `start` (default: cwd) to the nearest directory containing
    .agents/, .opencode/ or .git. The walk stops below the home directory:
    ~/.agents and ~/.opencode are user-scope, so eval copies placed there
    would show up in every OpenCode session. Falls back to `start`.
    """
    current = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    for parent in [current, *current.parents]:
        if parent == home or parent == Path(parent.anchor):
            break
        if any((parent / marker).exists() for marker in PROJECT_MARKERS):
            return parent
    return current


def resolve_project_root(explicit: str | None) -> Path:
    """Return the eval project root, refusing the home directory."""
    root = Path(explicit).resolve() if explicit else find_project_root()
    if root == Path.home().resolve():
        print(
            "Error: the eval project root resolved to the home directory; eval skill "
            "copies would become user-scope skills. Run from a project directory or "
            "pass --project-root.",
            file=sys.stderr,
        )
        sys.exit(1)
    return root


def warn_same_name_skills(project_root: Path, skill_name: str) -> None:
    """Warn when an installed skill shares the name of the skill under test."""
    home = Path.home()
    skill_dirs = [
        project_root / ".agents" / "skills",
        project_root / ".opencode" / "skills",
        project_root / ".opencode" / "skill",
        home / ".agents" / "skills",
        home / ".config" / "opencode" / "skills",
        home / ".config" / "opencode" / "skill",
    ]
    for skills_dir in skill_dirs:
        if not skills_dir.is_dir():
            continue
        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                name, _, _ = parse_skill_md(skill_md.parent)
            except Exception:
                continue
            if name == skill_name:
                print(
                    f"Warning: an installed skill named '{skill_name}' exists at "
                    f"{skill_md.parent}; loads of it count as triggers and can "
                    "produce false positives. Move it aside while evaluating.",
                    file=sys.stderr,
                )


def detect_trigger(line: str, skill_name: str) -> bool:
    """Return True if a JSON event line contains a skill tool call for skill_name.

    Matches both the plain skill name and uniquely suffixed eval copies
    (<skill_name>-skill-<id>), since all copies share the same description.
    """
    line = line.strip()
    if not line:
        return False
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return False
    part = event.get("part", {})
    if part.get("type") != "tool" or part.get("tool") != "skill":
        return False
    state = part.get("state", {})
    tool_input = state.get("input") or {}
    name = tool_input.get("name", "")
    return name == skill_name or name.startswith(f"{skill_name}-skill-")


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Installs a uniquely named copy of the skill under .agents/skills/ so it
    appears in the agent's available skills list, then runs `opencode run`
    with the raw query and inspects JSON tool events for a skill load.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    skill_dir = Path(project_root) / ".agents" / "skills" / clean_name
    skill_file = skill_dir / "SKILL.md"

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        indented_desc = "\n".join(f"  {line}" for line in skill_description.split("\n"))
        skill_file.write_text(
            "---\n"
            f"name: {clean_name}\n"
            "description: |\n"
            f"{indented_desc}\n"
            "---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )

        # The query goes in via stdin rather than argv: no command-line length
        # limit, and no re-parsing of `&`, `|`, `%` ... when Windows launches
        # the npm `opencode.cmd` shim through cmd.exe.
        cmd = [shutil.which(AGENT_CMD) or AGENT_CMD, "run", "--format", "json", "--auto"]
        if model:
            cmd.extend(["--model", model])

        env = {k: v for k, v in os.environ.items() if k != "OPENCODE"}
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )
        process.stdin.write(query.encode("utf-8"))
        process.stdin.close()

        # Read stdout on a thread (select() on pipes does not work on Windows).
        lines: queue.Queue = queue.Queue()

        def pump() -> None:
            for raw in iter(process.stdout.readline, b""):
                lines.put(raw)
            lines.put(None)

        threading.Thread(target=pump, daemon=True).start()

        triggered = False
        deadline = time.time() + timeout
        try:
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    raw = lines.get(timeout=min(1.0, remaining))
                except queue.Empty:
                    continue
                if raw is None:
                    break
                if detect_trigger(raw.decode("utf-8", errors="replace"), skill_name):
                    triggered = True
                    break
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered
    finally:
        if skill_file.exists():
            skill_file.unlink()
        if skill_dir.exists():
            skill_dir.rmdir()


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model for opencode run (default: user's configured model)")
    parser.add_argument("--project-root", default=None, help="Project to run the evals in (default: nearest ancestor of cwd with .agents/, .opencode/ or .git)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = resolve_project_root(args.project_root)
    warn_same_name_skills(project_root, name)

    if args.verbose:
        print(f"Project root: {project_root}", file=sys.stderr)
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
