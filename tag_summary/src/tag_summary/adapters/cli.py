"""CLI tag_summary.

Команды:
    run         — прогнать все этапы (остановка на approve)
    collect     — сбор кандидатов
    aggregate   — подсчёт частот
    cluster     — кластеризация
    approve     — утвердить финальный список тегов
    apply       — применить утверждённые теги к файлам
    validate    — валидация результата
    probe       — диагностический прогон одного файла
    probe-many  — диагностический прогон нескольких файлов
    status      — состояние запуска
    list-runs   — список запусков
    test        — pre-flight проверки
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from tag_summary.adapters.facade import TagSummary
from tag_summary.domain.exceptions import (
    CacheError,
    ConfigError,
    FileReadError,
    FileWriteError,
    LLMError,
    LLMFormatError,
    TagSummaryError,
)

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.debug)

    try:
        return _dispatch(args)
    except ConfigError as exc:
        logger.error("ConfigError: %s", exc)
        return 2
    except LLMFormatError as exc:
        logger.error("LLMFormatError: %s", exc)
        return 3
    except LLMError as exc:
        logger.error("LLMError: %s", exc)
        return 3
    except (FileReadError, FileWriteError) as exc:
        logger.error("FileError: %s", exc)
        return 4
    except (CacheError, TagSummaryError) as exc:
        logger.error("TagSummaryError: %s", exc)
        return 5
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tag_summary", description="AI tag pipeline for Obsidian")
    p.add_argument("--vault", help="Path to Obsidian vault root")
    p.add_argument("--runs-dir", help="Directory to store run artifacts")
    p.add_argument("--config", help="Path to config.toml")
    p.add_argument(
        "--backend",
        choices=("local", "web", "custom"),
        help="LLM backend: local (Ollama), web (ActantAI) or custom (manual via files)",
    )
    p.add_argument(
        "--parallel",
        type=int,
        help="Max parallel LLM requests (1..8)",
    )
    p.add_argument(
        "--files-per-batch",
        type=int,
        help="Files per custom-mode batch (1..16)",
    )
    p.add_argument("--debug", action="store_true", help="Enable DEBUG logging")

    sub = p.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run all stages (stops at approve)")
    run_p.add_argument("--threshold", type=int, default=None)

    for name in ("collect", "aggregate", "cluster", "apply", "validate"):
        sp = sub.add_parser(name, help=f"Run only the '{name}' stage")
        sp.add_argument("--run", help="Existing run id to continue")
        if name == "aggregate":
            sp.add_argument("--threshold", type=int, default=None)
        if name == "apply":
            sp.add_argument(
                "--limit",
                type=int,
                default=None,
                help="Process only first N files (for testing)",
            )

    probe_p = sub.add_parser("probe", help="Diagnose one file (no cache writes)")
    probe_p.add_argument("--path", required=True, help="Vault-relative path to .md file")
    probe_p.add_argument("--run", help="Existing run id (optional)")
    probe_p.add_argument("--save-json", help="Save full dump to a JSON file")

    pm_p = sub.add_parser("probe-many", help="Diagnose several files (no cache writes)")
    pm_p.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Vault-relative paths to .md files (space-separated)",
    )
    pm_p.add_argument("--run", help="Existing run id (optional)")
    pm_p.add_argument("--save-json", help="Save full dumps array to a JSON file")

    approve_p = sub.add_parser("approve", help="Approve final tag list")
    approve_p.add_argument("--run", help="Existing run id")
    approve_p.add_argument("--tags-file", required=True, help="Path to JSON array")

    status_p = sub.add_parser("status", help="Show run status")
    status_p.add_argument("--run", help="Existing run id (default: latest)")

    sub.add_parser("list-runs", help="List all runs")
    sub.add_parser("test", help="Run pre-flight environment checks")

    return p


def _dispatch(args: argparse.Namespace) -> int:
    cmd = args.command
    if cmd == "list-runs":
        return _cmd_list_runs(args)
    if cmd == "test":
        return _cmd_test(args)
    if cmd == "status":
        return _cmd_status(args)
    if cmd == "run":
        return _cmd_run(args)
    if cmd == "approve":
        return _cmd_approve(args)
    if cmd == "probe":
        return _cmd_probe(args)
    if cmd == "probe-many":
        return _cmd_probe_many(args)
    return _cmd_stage(args, cmd)


def _cmd_run(args: argparse.Namespace) -> int:
    with TagSummary(
        vault_path=args.vault,
        runs_dir=args.runs_dir,
        threshold=args.threshold,
        backend=getattr(args, "backend", None),
        parallel=getattr(args, "parallel", None),
        config_path=args.config,
    ) as ts:
        print(f"Run id: {ts.run_id}")
        print(f"Artifacts: {ts.run_path}")
        if not ts.context.is_done("collect"):
            n = ts.collect()
            print(f"collect: {n} files processed")
        if not ts.context.is_done("aggregate"):
            ts.aggregate()
            print("aggregate: done")
        if not ts.context.is_done("cluster"):
            r = ts.cluster()
            print(f"cluster: {r.get('total_clusters', 0)} clusters")
        if not ts.context.is_done("apply"):
            if not ts.context.is_done("approve"):
                print(
                    "\nApprove stage requires manual confirmation.\n"
                    f"1. Review {ts.run_path / '03_clusters.json'}\n"
                    f"2. Prepare a JSON array of approved tags\n"
                    f"3. Run: tag_summary approve --run {ts.run_id} --tags-file <path>\n"
                    f"4. Then: tag_summary apply --run {ts.run_id}"
                )
                return 0
            n = ts.apply()
            print(f"apply: {n} files updated")
        if not ts.context.is_done("validate"):
            ts.validate()
            print("validate: done")
        return 0


def _cmd_stage(args: argparse.Namespace, stage: str) -> int:
    kwargs = {
        "vault_path": args.vault,
        "runs_dir": args.runs_dir,
        "config_path": args.config,
        "backend": getattr(args, "backend", None),
        "parallel": getattr(args, "parallel", None),
        "files_per_batch": getattr(args, "files_per_batch", None),
    }
    if stage == "aggregate" and getattr(args, "threshold", None) is not None:
        kwargs["threshold"] = args.threshold
    run_id = getattr(args, "run", None)
    if run_id:
        kwargs["run_id"] = run_id

    with TagSummary(**kwargs) as ts:
        if stage == "collect":
            n = ts.collect()
            print(f"collect: {n} files processed")
        elif stage == "aggregate":
            r = ts.aggregate()
            print(f"aggregate: {r['total_unique_tags']} unique, {r['filtered_count']} kept")
        elif stage == "cluster":
            r = ts.cluster()
            print(f"cluster: {r['total_clusters']} clusters")
        elif stage == "apply":
            n = ts.apply(limit=getattr(args, "limit", None))
            print(f"apply: {n} files updated")
        elif stage == "validate":
            r = ts.validate()
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"Unknown stage: {stage}", file=sys.stderr)
            return 1
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    kwargs = {
        "vault_path": args.vault,
        "runs_dir": args.runs_dir,
        "config_path": args.config,
        "backend": getattr(args, "backend", None),
        "parallel": getattr(args, "parallel", None),
    }
    if args.run:
        kwargs["run_id"] = args.run

    with TagSummary(**kwargs) as ts:
        print(f"# Probe: {args.path}")
        print(f"# Run: {ts.run_id}  (artifacts: {ts.run_path})")
        result = ts.probe(args.path)
        _print_probe_result(result)
        if args.save_json:
            out = Path(args.save_json)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
            print(f"\n[Full dump saved to {out}]")
    return 0


def _cmd_probe_many(args: argparse.Namespace) -> int:
    kwargs = {
        "vault_path": args.vault,
        "runs_dir": args.runs_dir,
        "config_path": args.config,
        "backend": getattr(args, "backend", None),
        "parallel": getattr(args, "parallel", None),
    }
    if args.run:
        kwargs["run_id"] = args.run

    with TagSummary(**kwargs) as ts:
        print(f"# Probe-many: {len(args.paths)} file(s)")
        print(f"# Run: {ts.run_id}  (artifacts: {ts.run_path})")
        all_results: list[dict] = []
        for rel_path in args.paths:
            print(f"\n{'=' * 60}")
            print(f"# {rel_path}")
            print('=' * 60)
            result = ts.probe(rel_path)
            all_results.append(result)
            _print_probe_result(result, verbose=False)
        if args.save_json:
            out = Path(args.save_json)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as fh:
                json.dump(all_results, fh, ensure_ascii=False, indent=2)
            print(f"\n[Full dumps saved to {out}]")
    return 0


def _print_probe_result(result: dict, *, verbose: bool = True) -> None:
    print("\n=== META ===")
    meta = {k: v for k, v in result.items()
            if k not in ("system_prompt", "user_prompt", "raw_response")}
    print(json.dumps(meta, ensure_ascii=False, indent=2))

    if verbose:
        print("\n=== SYSTEM PROMPT (first 800 chars) ===")
        print((result.get("system_prompt") or "")[:800])
        print("\n=== USER PROMPT (first 1500 chars) ===")
        print((result.get("user_prompt") or "")[:1500])

    print("\n=== RAW RESPONSE ===")
    print((result.get("raw_response") or "")[:2500])


def _cmd_approve(args: argparse.Namespace) -> int:
    tags_path = Path(args.tags_file)
    if not tags_path.exists():
        print(f"Tags file not found: {tags_path}", file=sys.stderr)
        return 1
    try:
        with tags_path.open("r", encoding="utf-8") as fh:
            tags = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to read tags file: {exc}", file=sys.stderr)
        return 1
    if not isinstance(tags, list):
        print("Tags file must contain a JSON array", file=sys.stderr)
        return 1

    kwargs = {
        "vault_path": args.vault,
        "runs_dir": args.runs_dir,
        "config_path": args.config,
    }
    if args.run:
        kwargs["run_id"] = args.run
    with TagSummary(**kwargs) as ts:
        result = ts.approve([str(t) for t in tags])
        print(f"approve: {result['count']} tags recorded in run {ts.run_id}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    kwargs = {
        "vault_path": args.vault,
        "runs_dir": args.runs_dir,
        "config_path": args.config,
    }
    if args.run:
        kwargs["run_id"] = args.run
    else:
        rid = _latest_run_id(Path(args.runs_dir) if args.runs_dir else None)
        if rid is None:
            print("No runs found", file=sys.stderr)
            return 1
        kwargs["run_id"] = rid
    with TagSummary(**kwargs) as ts:
        print(json.dumps(ts.status(), ensure_ascii=False, indent=2))
    return 0


def _cmd_list_runs(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir) if args.runs_dir else _default_runs_dir()
    if not runs_dir.exists():
        print(f"Runs directory does not exist: {runs_dir}")
        return 0
    runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    if not runs:
        print("No runs found")
        return 0
    for r in runs:
        manifest = r / "manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                stages = data.get("stages", {})
                done = sum(1 for s in stages.values() if s.get("status") == "done")
                print(f"{r.name}  stages_done={done}/{len(stages)}")
            except (OSError, json.JSONDecodeError):
                print(f"{r.name}  (manifest unreadable)")
        else:
            print(f"{r.name}  (no manifest)")
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    print("Pre-flight checks:")
    ok = True

    for mod in ("ai_talk", "jasonutils", "command_engine"):
        try:
            __import__(mod)
            print(f"  [OK] {mod} importable")
        except ImportError as exc:
            print(f"  [FAIL] {mod} not importable: {exc}")
            ok = False

    try:
        from tag_summary.config.settings import load_settings
        s = load_settings(vault_path=args.vault)
        print(f"  [OK] settings loaded: vault={s.vault_path}")
        print(f"  [OK] runs dir: {s.runs_dir}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] settings: {exc}")
        ok = False

    print("\nResult:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _default_runs_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "runs"


def _latest_run_id(runs_dir: Path | None) -> str | None:
    if runs_dir is None:
        runs_dir = _default_runs_dir()
    if not runs_dir.exists():
        return None
    runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    return runs[0].name if runs else None


if __name__ == "__main__":
    sys.exit(main())
