"""Build a validated patch package from Firecrawl-scraped Lolalytics pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PATCH = "16.14"
SOURCE_DIR = ROOT / ".firecrawl"
OUTPUT_DIR = ROOT / "data" / PATCH
BASE_PATCH_DIR = ROOT / "data" / "16.13"
ROLE_SOURCES = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MID": "middle",
    "ADC": "bottom",
    "SUPPORT": "support",
}


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def canonical(value: str) -> str:
    return "".join(char for char in value if char.isalnum()).lower()


def champion_index() -> dict[str, str]:
    index: dict[str, str] = {}
    payload = read_json(ROOT / "data" / "zh_CN" / "champion.json", {})
    for champion_id, champion in payload.get("data", {}).items():
        index[canonical(champion_id)] = champion_id
        for field in ("name", "title", "id"):
            value = champion.get(field)
            if value:
                index.setdefault(canonical(str(value)), champion_id)
    return index


def firecrawl_command() -> str:
    configured = os.environ.get("FIRECRAWL_BIN")
    if configured:
        return configured
    candidate = Path(os.environ.get("APPDATA", "")) / "npm" / "firecrawl.cmd"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("Firecrawl CLI not found. Set FIRECRAWL_BIN or run firecrawl init.")


def scrape(url: str, output_path: Path) -> None:
    if output_path.exists() and output_path.stat().st_size > 1_000:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [firecrawl_command(), "scrape", "-u", url, "-o", str(output_path)],
        cwd=ROOT,
        check=True,
    )


def parse_tierlist(path: Path, role: str, known: dict[str, str]) -> dict[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: dict[str, dict[str, Any]] = {}
    for index, line in enumerate(lines):
        name_match = re.match(r"^\[([^\]]+)\]\(https://lolalytics\.com/lol/[^/]+/build/", line)
        if not name_match:
            continue
        values = [value.strip() for value in lines[index + 1 :] if value.strip()]
        if len(values) < 9 or not re.fullmatch(r"[SABCD][+-]?", values[0]):
            continue
        lane_match = re.search(r"\)([\d.]+)$", values[1])
        if not lane_match:
            continue
        champion = known.get(canonical(name_match.group(1)))
        if not champion:
            continue
        try:
            winrate = float(values[2])
            pickrate = float(values[4])
            banrate = float(values[5])
            games = int(values[7].replace(",", ""))
        except ValueError:
            continue
        meta_score = winrate * 0.5 + pickrate * 0.3 + banrate * 0.2
        entries[champion] = {
            "winrate": round(winrate, 2),
            "pickrate": round(pickrate, 2),
            "banrate": round(banrate, 2),
            "tier": values[0],
            "games": games,
            "sample_confidence": 1.0 if games >= 1_500 else 0.75,
            "meta_score": round(meta_score, 2),
            "champion": champion,
            "display_name": champion,
            "role": role,
            "source": "lolalytics_firecrawl",
        }
    return entries


def parse_counters(path: Path, champion: str, role: str, known: dict[str, str]) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, Any]] = {}
    heading_expression = re.compile(
        r"\n# (?P<name>[^\n]+)\n\n## [^\n]+\n\n"
        r"(?P<body>.*?)(?=\n# [^\n]+\n\n## |\Z)",
        re.DOTALL,
    )
    for match in heading_expression.finditer(text):
        opponent = known.get(canonical(match.group("name")))
        if not opponent or opponent == champion:
            continue
        body = match.group("body")
        outcome = re.search(
            r"After normalising.*?wins against [^\n]+?(?P<delta>[\d.]+)%"
            r"(?P<direction>less|more) often",
            body,
            re.DOTALL,
        )
        if not outcome:
            continue
        delta = float(outcome.group("delta"))
        if outcome.group("direction") == "less":
            delta = -delta
        previous_text = text[max(0, match.start() - 1800):match.start()]
        games_match = re.findall(r"([\d,]+) Games", previous_text)
        games = int(games_match[-1].replace(",", "")) if games_match else 0
        confidence = 1.0 if games >= 1_500 else (0.75 if games >= 500 else max(0.25, games / 500 * 0.5))
        result[opponent] = {
            "role": role,
            "winrate_delta": round(delta, 2),
            "counter_score": round(max(0, min(100, 50 + delta * confidence * 5)), 2),
            "games": games,
            "source": "lolalytics_firecrawl",
        }
    return result


def scrape_tierlists() -> None:
    for role, lane in ROLE_SOURCES.items():
        scrape(
            f"https://lolalytics.com/lol/tierlist/?lane={lane}",
            SOURCE_DIR / f"tierlist-{lane}.md",
        )


def scrape_counter_pages(meta: dict[str, Any]) -> None:
    for role, lane in ROLE_SOURCES.items():
        for champion in meta.get("roles", {}).get(role, {}):
            path = SOURCE_DIR / "counters" / f"{champion.lower()}-{lane}.md"
            scrape(
                f"https://lolalytics.com/lol/{champion.lower()}/counters/?lane={lane}",
                path,
            )


def build_package() -> dict[str, Any]:
    known = champion_index()
    base_meta = read_json(BASE_PATCH_DIR / "meta_data.json", {})
    base_counters = read_json(BASE_PATCH_DIR / "counter_data.json", {})
    roles = base_meta.get("roles", {})
    updated_roles: dict[str, int] = {}

    for role, lane in ROLE_SOURCES.items():
        entries = parse_tierlist(SOURCE_DIR / f"tierlist-{lane}.md", role, known)
        if len(entries) < 15:
            raise RuntimeError(f"{role} tier list only produced {len(entries)} valid entries")
        roles.setdefault(role, {}).update(entries)
        updated_roles[role] = len(entries)

    champions: dict[str, dict[str, Any]] = {}
    for role, entries in roles.items():
        for champion, entry in entries.items():
            record = champions.setdefault(champion, {"roles": {}, "best_role": role, "best_meta_score": -1})
            record["roles"][role] = entry
            if entry.get("meta_score", 0) >= record["best_meta_score"]:
                record["best_role"] = role
                record["best_meta_score"] = entry.get("meta_score", 0)

    meta = {
        "patch": PATCH,
        "source": "lolalytics_firecrawl_16_14",
        "fallback_patch": "16.13",
        "tier": "emerald",
        "generated_at": int(time.time()),
        "roles": roles,
        "champions": champions,
        "coverage": {"updated_roles": updated_roles, "updated_entries": sum(updated_roles.values())},
    }

    role_matchups = base_counters.get("role_matchups", {})
    counter_champions = base_counters.get("champions", {})
    updated_counters = 0
    failed_counters: list[dict[str, str]] = []
    for role, lane in ROLE_SOURCES.items():
        for champion in meta["roles"][role]:
            path = SOURCE_DIR / "counters" / f"{champion.lower()}-{lane}.md"
            if not path.exists():
                continue
            pairs = parse_counters(path, champion, role, known)
            if not pairs:
                failed_counters.append({"champion": champion, "role": role})
                continue
            role_matchups.setdefault(role, {})[champion] = pairs
            if champions[champion]["best_role"] == role:
                counter_champions[champion] = pairs
            updated_counters += 1

    if updated_counters < 75:
        raise RuntimeError(f"Only {updated_counters} Firecrawl counter pages were valid")

    counters = {
        "patch": PATCH,
        "source": "lolalytics_firecrawl_16_14",
        "fallback_patch": "16.13",
        "tier": "emerald",
        "generated_at": int(time.time()),
        "coverage": {
            "updated_champion_roles": updated_counters,
            "failed": len(failed_counters),
            "pairs": sum(len(pairs) for candidates in role_matchups.values() for pairs in candidates.values()),
        },
        "failed": failed_counters,
        "champions": counter_champions,
        "role_matchups": role_matchups,
    }

    from analysis.online_meta_sync import OnlineMetaSync

    sync = OnlineMetaSync(PATCH)
    synergy = sync.build_full_synergy(meta)
    synergy["source"] = "tag_inferred_from_lolalytics_firecrawl_16_14"
    synergy["generated_at"] = int(time.time())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "meta_data.json", meta)
    write_json(OUTPUT_DIR / "counter_data.json", counters)
    write_json(OUTPUT_DIR / "synergy_data.json", synergy)
    sync._write_role_indexes(meta)

    patch_info = {
        "current_patch": PATCH,
        "latest_patch": PATCH,
        "updated_at": int(time.time()),
        "source": "firecrawl_lolalytics_validated",
    }
    write_json(ROOT / "data" / "patch_version.json", patch_info)
    return {
        "patch": PATCH,
        "meta_entries": meta["coverage"]["updated_entries"],
        "updated_counter_pages": updated_counters,
        "counter_failures": len(failed_counters),
        "synergy_champions": len(synergy.get("champions", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-tierlists", action="store_true")
    parser.add_argument("--fetch-counters", action="store_true")
    parser.add_argument("--build", action="store_true")
    arguments = parser.parse_args()
    if arguments.fetch_tierlists:
        scrape_tierlists()
    if arguments.fetch_counters:
        known = champion_index()
        roles = {
            role: parse_tierlist(SOURCE_DIR / f"tierlist-{lane}.md", role, known)
            for role, lane in ROLE_SOURCES.items()
        }
        scrape_counter_pages({"roles": roles})
    if arguments.build:
        print(json.dumps(build_package(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
