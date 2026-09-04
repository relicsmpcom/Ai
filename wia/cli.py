"""Command line interface.

    wia detect essay.txt
    wia humanize draft.md --mode zakelijk_nederlands --locale nl-NL
    wia analyze post.txt
    wia compare original.txt rewrite.txt
    wia style sample1.txt sample2.txt
    wia bench --cv 5 --markdown docs/EVALUATION.md
    wia train
    wia serve
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

BAR = "█"


def _read(source: str) -> str:
    """Accept a path, stdin, or literal text.

    Long literals are common here — people paste a paragraph straight onto the
    command line — so the path check has to survive a filename far longer than
    the filesystem allows.
    """
    if source == "-":
        return sys.stdin.read()
    if len(source) < 4096 and "\n" not in source:
        try:
            path = Path(source)
            if path.exists():
                return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return source


def _bar(value: float, width: int = 24) -> str:
    filled = int(round(value * width))
    return BAR * filled + "·" * (width - filled)


def _emit(payload, as_json: bool) -> bool:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return True
    return False


# ---------------------------------------------------------------- detect ---
def cmd_detect(args: argparse.Namespace) -> int:
    from wia.detector import Detector

    text = _read(args.text)
    result = Detector.load().detect(text, language=args.language,
                                    with_segments=not args.no_segments)
    if _emit(result.to_dict(), args.json):
        return 0

    print(f"\n  {result.label.label}  ({result.confidence.value} confidence)")
    print(f"  {result.words} words · {result.language.value.upper()} · "
          f"domain: {result.domain}\n")
    for name, value in (("likely human", result.human_probability),
                        ("mixed / assisted", result.mixed_probability),
                        ("likely AI", result.ai_probability)):
        print(f"  {name:>17}  {_bar(value)}  {value:5.1%}")
    if result.mixed_authorship:
        m = result.mixed_authorship
        print(f"\n  spans: {m['verdict']} — {m['ai_span_share']:.0%} of the text "
              f"reads as AI-like across {m['segment_count']} windows")
    if result.explanations:
        print("\n  what moved this estimate:")
        for line in result.explanations:
            print(f"    · {line}")
    if result.warnings:
        print("\n  warnings:")
        for line in result.warnings:
            print(f"    ! {line}")
    print("\n  This is an estimate, not proof. Never use it alone to accuse anyone.\n")
    return 0


# -------------------------------------------------------------- humanize ---
def cmd_humanize(args: argparse.Namespace) -> int:
    from wia.humanizer import HumanizeOptions, Humanizer, StyleProfile

    text = _read(args.text)
    profile = None
    if args.profile:
        profile = StyleProfile.from_dict(json.loads(Path(args.profile).read_text(encoding="utf-8")))
    options = HumanizeOptions.from_dict({
        k: v for k, v in vars(args).items()
        if k in HumanizeOptions.__dataclass_fields__ and v is not None
    })
    result = Humanizer().humanize(text, options, profile)
    if _emit(result.to_dict(), args.json):
        return 0

    if result.plan.get("findings"):
        print("\n  found: " + "; ".join(result.plan["findings"]))
    for c in result.candidates:
        mark = " ← recommended" if c.label == result.recommended else ""
        print(f"\n  [{c.label}] {c.description}{mark}")
        if not c.accepted:
            print(f"      rejected: {c.rejected_reason} (showing the original)")
        print()
        for line in c.text.split("\n"):
            print(f"      {line}")
        s = c.score
        print(f"\n      meaning {s.meaning_preservation:.0f} · naturalness {s.naturalness:.0f}"
              f" · grammar {s.grammar:.0f} · tone {s.tone_match:.0f} · overall {s.overall:.0f}")
    for warning in result.warnings:
        print(f"\n  ! {warning}")
    print(f"\n  {result.notes[0]}\n" if result.notes else "")
    return 0


# --------------------------------------------------------------- analyze ---
def cmd_analyze(args: argparse.Namespace) -> int:
    from wia.analyze import analyze

    report = analyze(_read(args.text), args.language, with_detection=not args.no_detection)
    if _emit(report.to_dict(), args.json):
        return 0
    print(f"\n  {report.words} words · {report.sentences} sentences · "
          f"{report.paragraphs} paragraphs · ~{max(1, report.reading_seconds // 60)} min read")
    print(f"  reading ease {report.readability['score']:.0f} — {report.readability['label']}")
    print(f"  rhythm: {report.rhythm['mean']} words average, variation "
          f"{report.rhythm['variation']:.2f} (shortest {report.rhythm['shortest']}, "
          f"longest {report.rhythm['longest']})")
    print(f"  tone: {report.tone['formality']['label']} "
          f"({report.tone['formality']['level']}/6) · naturalness "
          f"{report.naturalness['score']:.0f}/100")
    if report.issues:
        print("\n  what to look at:")
        for issue in report.issues:
            print(f"    [{issue.severity}] {issue.message}")
            for example in issue.examples[:2]:
                print(f"           “{example}”")
    if report.detection:
        d = report.detection
        print(f"\n  authorship estimate: {d['label_text']} "
              f"(human {d['human_probability']:.0%} / mixed {d['mixed_probability']:.0%} "
              f"/ AI {d['ai_probability']:.0%})")
    print()
    return 0


# --------------------------------------------------------------- compare ---
def cmd_compare(args: argparse.Namespace) -> int:
    from wia.analyze import compare

    result = compare(_read(args.original), _read(args.rewrite), args.language)
    if _emit(result, args.json):
        return 0
    m = result["meaning"]
    print(f"\n  meaning preserved: {'yes' if m['passed'] else 'NO'} ({m['score']:.0%})")
    for violation in m["violations"]:
        flag = "BLOCKING" if violation["blocking"] else "note"
        print(f"    [{flag}] {violation['detail']}")
    print("\n  deltas:")
    for key, value in result["deltas"].items():
        if value is None:
            continue
        print(f"    {key:22} {value:+}")
    print()
    return 0


# ----------------------------------------------------------------- style ---
def cmd_style(args: argparse.Namespace) -> int:
    from wia.humanizer import extract_style

    samples = [_read(s) for s in args.samples]
    profile = extract_style(samples, args.language, args.locale)
    if args.out:
        Path(args.out).write_text(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
                                  encoding="utf-8")
    if _emit(profile.to_dict(), args.json):
        return 0
    words = sum(len(s.split()) for s in samples)
    print(f"\n  profile {profile.id} · {profile.n_samples} samples · {words} words")
    for line in profile.describe():
        print(f"    · {line}")
    if words < 300:
        print("\n  ! Under 300 words is a sketch, not a fingerprint. Add more of your writing.")
    if args.out:
        print(f"\n  written to {args.out}")
    print()
    return 0


# ----------------------------------------------------------------- bench ---
def cmd_bench(args: argparse.Namespace) -> int:
    from wia.bench import Dataset, render_markdown, run_cross_validation, run_eval, validate

    dataset = Dataset.load()
    problems = validate(dataset.samples)
    if problems:
        print("dataset problems:")
        for p in problems[:20]:
            print("  -", p)
        return 1
    if args.summary:
        print(json.dumps(dataset.summary(), indent=2))
        return 0
    reports = []
    if args.cv:
        reports.append(run_cross_validation(folds=args.cv))
    if args.split:
        reports.append(run_eval(split=None if args.split == "all" else args.split))
    if not reports:
        reports.append(run_eval(split="test"))
    if args.json:
        print(json.dumps(reports, indent=2, default=float))
        return 0
    body = "\n\n".join(render_markdown(r) for r in reports)
    if args.markdown:
        Path(args.markdown).write_text(body, encoding="utf-8")
        print(f"written to {args.markdown}")
    else:
        print(body)
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from wia.bench.train import train_detector

    report = train_detector(out_path=Path(args.out) if args.out else None,
                            target_fpr=args.target_fpr)
    print(json.dumps(report.to_dict(), indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed: pip install 'wia[api]'", file=sys.stderr)
        return 1
    uvicorn.run("wia.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    from wia.features import FEATURES

    if args.json:
        print(json.dumps([{"name": f.name, "group": f.group, "description": f.doc,
                           "tends_toward": f.direction,
                           "used_as_authorship_evidence": f.authorship_evidence}
                          for f in FEATURES], indent=2))
        return 0
    group = ""
    for f in FEATURES:
        if f.group != group:
            group = f.group
            print(f"\n{group.upper()}")
        arrow = {"ai": "→ ai", "human": "→ human", None: ""}[f.direction]
        gate = "" if f.authorship_evidence else "  [measured only — never votes]"
        print(f"  {f.name:34} {arrow:9} {f.doc}{gate}")
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wia",
        description="Writing intelligence for Dutch and English: authorship "
                    "estimation, meaning-preserving rewriting, writing analysis.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", help="estimate how a text was likely produced")
    p.add_argument("text", help="file path, literal text, or - for stdin")
    p.add_argument("--language", default="auto", choices=["auto", "nl", "en"])
    p.add_argument("--no-segments", action="store_true", help="skip the span heatmap")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("humanize", help="rewrite for naturalness without changing meaning")
    p.add_argument("text", help="file path, literal text, or - for stdin")
    p.add_argument("--language", default="auto")
    p.add_argument("--locale", default=None)
    p.add_argument("--mode", default=None, help="named mode, e.g. zakelijk_nederlands")
    p.add_argument("--tone", default=None)
    p.add_argument("--formality", type=int, default=None, choices=range(1, 7))
    p.add_argument("--directness", default=None)
    p.add_argument("--conciseness", default=None)
    p.add_argument("--complexity", default=None)
    p.add_argument("--vocabulary", default=None)
    p.add_argument("--contractions", default=None)
    p.add_argument("--audience", default=None)
    p.add_argument("--purpose", default=None)
    p.add_argument("--sentence-variation", dest="sentence_variation", type=float, default=None)
    p.add_argument("--preserve", nargs="*", default=None, help="phrases to keep verbatim")
    p.add_argument("--candidates", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--profile", help="path to a style profile JSON")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_humanize)

    p = sub.add_parser("analyze", help="describe what is going on in a text")
    p.add_argument("text")
    p.add_argument("--language", default="auto")
    p.add_argument("--no-detection", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("compare", help="compare two versions, meaning first")
    p.add_argument("original")
    p.add_argument("rewrite")
    p.add_argument("--language", default="auto")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("style", help="build a Style DNA profile from your own writing")
    p.add_argument("samples", nargs="+")
    p.add_argument("--language", default="auto")
    p.add_argument("--locale", default="")
    p.add_argument("--out", help="write the profile to this path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_style)

    p = sub.add_parser("bench", help="run HumanBench-NL/EN")
    p.add_argument("--split", choices=["train", "dev", "test", "all"], default=None)
    p.add_argument("--cv", type=int, default=0, help="k-fold cross-validation")
    p.add_argument("--markdown", help="write the report to this path")
    p.add_argument("--summary", action="store_true", help="dataset composition only")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("train", help="train the detector on HumanBench")
    p.add_argument("--out", help="where to write weights.json")
    p.add_argument("--target-fpr", type=float, default=0.01)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("serve", help="run the API and web UI")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("features", help="list every measurement the detector uses")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_features)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
