"""
Measure the crime-vision pipeline against a labelled image set.

    docker compose exec api python scripts/eval_crime_vision.py
    docker compose exec api python scripts/eval_crime_vision.py --save-baseline
    docker compose exec api python scripts/eval_crime_vision.py --compare

Why this exists: "detection is poor" was a correct impression but an
unmeasurable one, and the pipeline has four stages that can each independently
be right or wrong. Without a baseline an improvement is indistinguishable from
a regression.

Two things it reports that a plain accuracy number does not:

* a **capability report** -- which object signals the decision engine scores
  against versus which YOLOv9c can physically emit. On the current build 11 of
  21 are impossible, which makes `vandalism` structurally unreachable. Some
  failures are vocabulary, not tuning, and conflating the two wastes effort.

* a **failure breakdown** by stage. "47% recall" is not actionable; "31 of 44
  misses never got past YOLO" tells you where to work.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# Run from backend/ so `app` is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.crime_decision_engine import CrimeDecisionEngine  # noqa: E402
from app.services.ai.crime_vision_service import (  # noqa: E402
    CrimeVisionService,
    get_crime_vision_service,
)

EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "eval" / "crime_vision"
MANIFEST = EVAL_DIR / "manifest.csv"
IMAGES = EVAL_DIR / "images"
BASELINE = EVAL_DIR / "baseline.json"

CLASSES = [
    "theft",
    "assault",
    "harassment",
    "vandalism",
    "burglary",
    "robbery",
    "none",
]


# ---------------------------------------------------------------------------
# Capability report
# ---------------------------------------------------------------------------
def capability_report(service: CrimeVisionService) -> dict[str, Any]:
    """
    Which object signals can the engine actually receive?

    The decision engine scores against object labels. Those labels can only
    arrive via YOLO_TO_CRIME_MAP applied to YOLO's class list, so any label
    outside that image is dead weight -- it contributes zero score forever, and
    worse, a cross-validation gate that requires one can never open.
    """
    if not service.model_loaded:
        service.load_models()

    coco = set(service.model.names.values()) if service.model else set()
    emittable = {service.YOLO_TO_CRIME_MAP.get(c, c) for c in coco}

    wanted: set[str] = set()
    for profile in CrimeDecisionEngine.CRIME_PROFILES.values():
        for tier in ("strong", "moderate", "context"):
            wanted.update(profile["object_signals"].get(tier, []))

    impossible = sorted(wanted - emittable)

    # Is pose analysis actually running? crime_vision_service swallows a failed
    # PoseDetectionService init and continues "with object detection only", so
    # this is observed, not assumed.
    pose_live = service.pose_service is not None
    scene_live = service.scene_service is not None

    # Walk each crime's cross-validation gate and decide whether it can open at
    # all, given which objects are reachable and whether pose is live. A gate
    # with no satisfiable branch makes its class undetectable no matter how the
    # weights are tuned.
    gates: dict[str, dict[str, Any]] = {}
    for crime, profile in CrimeDecisionEngine.CRIME_PROFILES.items():
        cv = profile.get("cross_validation", {})
        reasons: list[str] = []
        reachable = True

        if cv.get("damage_evidence_required"):
            need = {"graffiti", "broken window", "damaged property"}
            if not (need & emittable):
                reachable = False
                reasons.append(f"needs damage evidence {sorted(need)} - none emittable")

        if cv.get("suspicious_action_required") and not pose_live:
            reachable = False
            reasons.append("needs a pose action, pose analysis is not running")

        if cv.get("interaction_required") and not pose_live:
            reachable = False
            reasons.append("needs pose interaction, pose analysis is not running")

        if cv.get("pose_required_if_no_weapon"):
            weapons = {"knife", "gun", "baseball bat"} & emittable
            if not weapons and not pose_live:
                reachable = False
                reasons.append("needs a weapon or a pose action; neither available")
            elif not pose_live:
                reasons.append(f"pose dead -> requires a visible {'/'.join(sorted(weapons))}")

        if cv.get("weapon_or_threat_required"):
            weapons = {"gun", "knife"} & emittable
            if not weapons and not pose_live:
                reachable = False
                reasons.append("needs a weapon or threatening pose; neither available")
            elif not pose_live:
                reasons.append(f"pose dead -> requires a visible {'/'.join(sorted(weapons))}")

        if cv.get("entry_sign_or_night_required"):
            signs = {"broken window", "door"} & emittable
            if not signs:
                reasons.append("entry signs unreachable -> only detectable at night")

        gates[crime] = {"reachable": reachable, "reasons": reasons}

    return {
        "coco_classes": len(coco),
        "signals_wanted": len(wanted),
        "signals_reachable": sorted(wanted & emittable),
        "signals_impossible": impossible,
        "pose_analysis_live": pose_live,
        "scene_analysis_live": scene_live,
        "gates": gates,
        "structurally_unreachable_classes": sorted(
            c for c, g in gates.items() if not g["reachable"]
        ),
    }


# ---------------------------------------------------------------------------
# Running the set
# ---------------------------------------------------------------------------
def load_manifest() -> list[dict[str, str]]:
    if not MANIFEST.exists():
        raise SystemExit(
            f"No manifest at {MANIFEST}.\n"
            f"See {EVAL_DIR / 'README.md'} for the format and what to collect."
        )
    with MANIFEST.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("image") or "").strip()]
    if not rows:
        raise SystemExit(f"{MANIFEST} has no rows yet.")
    return rows


def classify_failure(expected: str, predicted: str | None, result: dict) -> str:
    """Attribute a miss to the stage responsible for it."""
    if expected == predicted:
        return "correct"
    if expected == "none":
        return "false_positive"

    message = (result.get("message") or "").lower()
    details = result.get("details") or {}
    objects = details.get("detected_objects") or result.get("detected_objects") or []
    pose = result.get("pose_analysis")

    if "no relevant objects" in message or not objects:
        return "no_objects_detected"
    if "validation_failed" in message:
        # The fusion engine scored candidates and rejected them all.
        return "validation_failed"
    if predicted is None and not pose:
        return "pose_missing"
    if predicted is None:
        return "no_crime_predicted"
    return "wrong_class"


async def run() -> dict[str, Any]:
    service = get_crime_vision_service()
    caps = capability_report(service)
    rows = load_manifest()

    records: list[dict[str, Any]] = []
    missing: list[str] = []

    for i, row in enumerate(rows, 1):
        name = row["image"].strip()
        expected = (row.get("expected") or "").strip().lower()
        path = IMAGES / name

        if not path.exists():
            missing.append(name)
            continue
        if expected not in CLASSES:
            raise SystemExit(
                f"{MANIFEST}: row {i} has expected={expected!r}; "
                f"must be one of {CLASSES}"
            )

        started = time.perf_counter()
        result = await service.analyze_crime_image(
            image_data=path.read_bytes(),
            confidence_threshold=0.25,
        )
        elapsed = time.perf_counter() - started

        predicted = result.get("crime_type")  # None when no crime
        details = result.get("details") or {}
        pose = result.get("pose_analysis") or {}
        scene = result.get("scene_analysis") or {}

        records.append(
            {
                "image": name,
                "expected": expected,
                "predicted": predicted,
                "correct": (predicted or "none") == expected,
                "confidence": result.get("confidence"),
                "failure": classify_failure(expected, predicted or "none", result),
                "objects": details.get("detected_objects")
                or result.get("detected_objects")
                or [],
                "person_count": details.get("person_count", 0),
                "poses_detected": pose.get("poses_detected", 0),
                "scene_type": scene.get("scene_type"),
                "scene_confidence": scene.get("scene_confidence"),
                "seconds": round(elapsed, 2),
                "notes": (row.get("notes") or "").strip(),
            }
        )
        mark = "ok " if records[-1]["correct"] else "MISS"
        print(
            f"  [{i:>3}/{len(rows)}] {mark} {name[:38]:<38} "
            f"expected={expected:<10} got={predicted or 'none':<10} "
            f"{elapsed:.1f}s"
        )

    return {"capability": caps, "records": records, "missing_files": missing}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score(records: list[dict[str, Any]]) -> dict[str, Any]:
    present = sorted({r["expected"] for r in records} | {
        (r["predicted"] or "none") for r in records
    })

    per_class = {}
    for cls in present:
        tp = sum(1 for r in records if r["expected"] == cls and (r["predicted"] or "none") == cls)
        fp = sum(1 for r in records if r["expected"] != cls and (r["predicted"] or "none") == cls)
        fn = sum(1 for r in records if r["expected"] == cls and (r["predicted"] or "none") != cls)
        support = sum(1 for r in records if r["expected"] == cls)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall
            else None
        )
        per_class[cls] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    matrix: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        matrix[r["expected"]][r["predicted"] or "none"] += 1

    n = len(records)
    return {
        "n": n,
        "accuracy": sum(1 for r in records if r["correct"]) / n if n else None,
        "per_class": per_class,
        "confusion": {k: dict(v) for k, v in matrix.items()},
        "failures": dict(Counter(r["failure"] for r in records if not r["correct"])),
        "mean_seconds": round(sum(r["seconds"] for r in records) / n, 2) if n else None,
        "pose_null_rate": (
            sum(1 for r in records if r["poses_detected"] == 0) / n if n else None
        ),
    }


def pct(v: float | None) -> str:
    return "  --  " if v is None else f"{v * 100:5.1f}%"


def report(out: dict[str, Any], summary: dict[str, Any]) -> None:
    caps = out["capability"]
    print()
    print("=" * 72)
    print("CAPABILITY  (what the engine can physically receive)")
    print("=" * 72)
    print(f"  YOLO classes available        : {caps['coco_classes']}")
    print(f"  object signals wanted         : {caps['signals_wanted']}")
    print(f"  reachable                     : {len(caps['signals_reachable'])}")
    print(f"  IMPOSSIBLE                    : {len(caps['signals_impossible'])}")
    if caps["signals_impossible"]:
        print(f"      {', '.join(caps['signals_impossible'])}")
    print(f"  pose analysis running         : {caps['pose_analysis_live']}")
    print(f"  scene analysis running        : {caps['scene_analysis_live']}")
    if not caps["pose_analysis_live"]:
        print("      !! PoseDetectionService failed to initialise. mediapipe 1.x")
        print("         removed the legacy mp.solutions API this code uses; the new")
        print("         surface is mediapipe.tasks.python.vision.PoseLandmarker.")
        print("         Every pose-dependent gate below is therefore closed.")

    print()
    print("  can each crime type EVER be returned?")
    for crime, g in sorted(caps["gates"].items()):
        state = "yes" if g["reachable"] else "NEVER"
        print(f"    {crime:<12} {state}")
        for r in g["reasons"]:
            print(f"         - {r}")

    print()
    print("=" * 72)
    print(f"ACCURACY   n={summary['n']}   overall={pct(summary['accuracy'])}")
    print("=" * 72)
    print(f"  {'class':<12} {'support':>7} {'prec':>7} {'recall':>7} {'f1':>7}")
    for cls, m in summary["per_class"].items():
        flag = ""
        if cls in caps["structurally_unreachable_classes"]:
            flag = "  <- structurally impossible"
        elif m["support"] and m["support"] < 10 and cls != "none":
            flag = "  <- support <10, treat as unmeasured"
        print(
            f"  {cls:<12} {m['support']:>7} {pct(m['precision'])} "
            f"{pct(m['recall'])} {pct(m['f1'])}{flag}"
        )

    print()
    print("  confusion (row = expected, col = predicted):")
    for expected, preds in sorted(summary["confusion"].items()):
        cells = ", ".join(f"{k}:{v}" for k, v in sorted(preds.items()))
        print(f"    {expected:<12} -> {cells}")

    if summary["failures"]:
        print()
        print("  failure attribution (which stage lost it):")
        for reason, count in sorted(summary["failures"].items(), key=lambda x: -x[1]):
            print(f"    {count:>4}  {reason}")

    print()
    print(f"  mean inference        : {summary['mean_seconds']}s (CPU, in container)")
    print(f"  images with NO pose   : {pct(summary['pose_null_rate'])}")
    if not caps["pose_analysis_live"]:
        print("      Expected: pose analysis is not running at all (see above).")
    else:
        print("      detect_poses appends at most one pose, so multi-person")
        print("      interaction remains unreachable (defect 5).")

    if out["missing_files"]:
        print()
        print(f"  !! {len(out['missing_files'])} manifest row(s) have no image file:")
        for m in out["missing_files"][:10]:
            print(f"       {m}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-baseline", action="store_true",
                    help="write baseline.json for later --compare")
    ap.add_argument("--compare", action="store_true",
                    help="diff this run against the saved baseline")
    ap.add_argument("--json", action="store_true", help="dump raw results")
    args = ap.parse_args()

    print(f"Evaluating against {MANIFEST.relative_to(MANIFEST.parent.parent.parent)}")
    out = asyncio.run(run())
    if not out["records"]:
        print("\nNo images scored. Add rows to manifest.csv and files to images/.")
        print(f"See {EVAL_DIR / 'README.md'}")
        return 1

    summary = score(out["records"])
    report(out, summary)

    if args.json:
        print()
        print(json.dumps({"summary": summary, "records": out["records"]}, indent=2))

    if args.compare:
        if not BASELINE.exists():
            print(f"\nNo baseline at {BASELINE}. Run --save-baseline first.")
        else:
            old = json.loads(BASELINE.read_text(encoding="utf-8"))["summary"]
            print()
            print("=" * 72)
            print("DELTA vs baseline")
            print("=" * 72)
            d = (summary["accuracy"] or 0) - (old["accuracy"] or 0)
            print(f"  accuracy  {pct(old['accuracy'])} -> {pct(summary['accuracy'])}  ({d * 100:+.1f} pts)")
            for cls in sorted(set(old["per_class"]) | set(summary["per_class"])):
                o = old["per_class"].get(cls, {})
                n = summary["per_class"].get(cls, {})
                if o.get("f1") is None and n.get("f1") is None:
                    continue
                od, nd = o.get("f1") or 0, n.get("f1") or 0
                print(f"  f1 {cls:<12} {pct(o.get('f1'))} -> {pct(n.get('f1'))}  ({(nd - od) * 100:+.1f} pts)")

    if args.save_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "capability": out["capability"],
                    "summary": summary,
                    "records": out["records"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nBaseline written to {BASELINE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
