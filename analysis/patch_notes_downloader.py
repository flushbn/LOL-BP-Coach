from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import requests
from lxml import html

from analysis.data_patch_manager import DATA_DIR, normalize_patch


RIOT_NOTES_URL = "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-{patch}-notes/"


class PatchNotesDownloadError(RuntimeError):
    pass


class PatchNotesDownloader:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def download(self, patch: str) -> dict[str, Any]:
        patch = normalize_patch(patch)
        riot_patch = f"26.{patch.split('.')[1]}"
        url = RIOT_NOTES_URL.format(patch=riot_patch.replace(".", "-"))
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "LoL-BP-Coach-Patch-Notes/1.0"},
                timeout=25,
            )
            response.raise_for_status()
            document = html.fromstring(response.content)
            payload = self._parse(document, patch, riot_patch, url)
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise PatchNotesDownloadError(f"Riot patch notes request failed: {exc}") from exc
        except Exception as exc:
            raise PatchNotesDownloadError(f"Riot patch notes parse failed: {exc}") from exc

        if not payload["champion_changes"] and not payload["item_changes"]:
            raise PatchNotesDownloadError("Riot patch notes contained no champion or item changes")
        target = self.data_dir / "patch_notes" / f"{patch}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=target.parent) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temporary = Path(handle.name)
        temporary.replace(target)
        return {"patch": patch, "riot_patch": riot_patch, "path": str(target), "champions": len(payload["champion_changes"]), "items": len(payload["item_changes"])}

    def _parse(self, document, patch: str, riot_patch: str, url: str) -> dict[str, Any]:
        headings = document.xpath("//h2 | //h3")
        section = ""
        champions: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        runes: list[dict[str, Any]] = []
        systems: list[dict[str, Any]] = []
        for heading in headings:
            title = self._clean(heading.text_content())
            if heading.tag == "h2":
                section = title.lower()
                continue
            if not title or section not in {"champions", "items", "runes", "system changes"}:
                continue
            block = heading.getparent()
            summary = self._clean(" ".join(block.xpath(".//blockquote[1]//text()")))
            if not summary:
                summary = self._clean(" ".join(block.xpath(".//h4[1]/following-sibling::*[1]//text()")))
            row = {
                "champion": title,
                "type": self._change_type(summary),
                "description": summary or "Riot 官方版本改动，详情请查看来源公告。",
                "impact_tags": self._impact_tags(section, summary),
            }
            if section == "champions":
                champions.append(row)
            elif section == "items":
                items.append({**row, "item": row.pop("champion")})
            elif section == "runes":
                runes.append({**row, "rune": row.pop("champion")})
            else:
                systems.append({**row, "name": row.pop("champion")})
        return {
            "patch": patch,
            "riot_patch": riot_patch,
            "source": "Riot Games official patch notes",
            "source_url": url,
            "champion_changes": champions,
            "item_changes": items,
            "rune_changes": runes,
            "system_changes": systems,
            "meta_impacts": [],
        }

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _change_type(summary: str) -> str:
        text = summary.lower()
        if any(word in text for word in (" nerf", "nerf", "reduce", "decrease", "lower", "soften")):
            return "nerf"
        if any(word in text for word in (" buff", "buff", "increase", "raise", "strengthen")):
            return "buff"
        return "adjust"

    @staticmethod
    def _impact_tags(section: str, summary: str) -> list[str]:
        text = summary.lower()
        tags = []
        for keyword in ("top", "jungle", "mid", "bot", "support", "early", "late", "scaling", "damage", "tank"):
            if keyword in text:
                tags.append(keyword)
        return tags or ([section.lower()] if section else [])
