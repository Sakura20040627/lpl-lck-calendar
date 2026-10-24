#!/usr/bin/env python3
"""International-only LoL calendar: matches with at least one LPL team.

Rules (2026-10-24):
- Only international tournaments (Worlds, MSI, First Stand, EWC, and future
  Riot cross-region events). Regional leagues and domestic cups never appear.
- A match is included only if at least one participating team belongs to the
  current LPL roster (derived from the LPL league schedule of the season).
- Anyone's Legend (AL) is a regular LPL team: its matches are included like
  any other LPL team's (rule changed 2026-10-24; AL is no longer excluded).
- If the upstream schedule API fails, the previously published calendar is
  kept untouched; an empty result never overwrites it.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "lpl-lck-all-matches.ics"
FALLBACK_PATH = ROOT / "src" / "fallback_fixtures.json"
API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"  # public site key
BASE_URLS = (
    "https://esports-api.lolesports.com/persisted/gw",
    "https://prod-relapi.ewp.gg/persisted/gw",
)
# The LPL league schedule is fetched only to derive the current LPL roster;
# regional-league matches themselves are never published.
ROSTER_LEAGUE = "lpl"
# Known Riot international tournaments. Future cross-region events whose slug
# starts with one of these prefixes (e.g. "ewc_lol_2027") are picked up too;
# anything else must be added here explicitly after verifying its nature.
INTERNATIONAL_TOURNAMENTS = ("worlds", "msi", "first_stand", "ewc_lol")
INTERNATIONAL_PREFIXES = ("worlds", "msi", "first_stand", "ewc")
LABELS = {
    "msi": "季中冠军赛", "worlds": "全球总决赛",
    "first_stand": "全球先锋赛", "ewc_lol": "电竞世界杯",
}
PLACEHOLDERS = {"", "tbd", "to be determined", "待定", "unknown", "0", "tba"}
KEEP_DAYS = 30


class ScheduleError(RuntimeError):
    pass


def api(path, params):
    query = urllib.parse.urlencode(params)
    error = None
    for base in BASE_URLS:
        for attempt in range(2):
            url = base + "/" + path + "?" + query
            req = urllib.request.Request(url, headers={
                "x-api-key": API_KEY,
                "Accept": "application/json",
                "User-Agent": "CNKR-Esports-Calendar/1.0",
            })
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    body = json.load(response)
                if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
                    raise ScheduleError("API returned invalid data")
                return body
            except (OSError, ValueError, ScheduleError) as exc:
                error = exc
                time.sleep(1 + attempt)
    raise ScheduleError(f"{path}: {error}")


def is_international_slug(slug):
    """True for known international tournaments and future editions of them.

    Regional leagues (lpl, lck, lec, lcs, lcp, ...), domestic cups
    (demacia_cup, kespa_cup) and promotion tournaments never match.
    """
    if not isinstance(slug, str):
        return False
    slug = slug.strip().casefold()
    if slug in INTERNATIONAL_TOURNAMENTS:
        return True
    return any(slug.startswith(prefix + "_") for prefix in INTERNATIONAL_PREFIXES)


def leagues():
    """Return {slug: league_id} for the LPL roster source + internationals."""
    data = api("getLeagues", {"hl": "zh-CN"})
    items = data["data"].get("leagues")
    if not isinstance(items, list):
        raise ScheduleError("missing leagues in API response")
    found = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "")
        if item.get("id") and (slug == ROSTER_LEAGUE or is_international_slug(slug)):
            found[slug] = str(item["id"])
    if ROSTER_LEAGUE not in found:
        raise ScheduleError("LPL league ID missing; refusing to publish")
    if not any(slug != ROSTER_LEAGUE for slug in found):
        raise ScheduleError("No international league available; refusing to publish")
    for missing in set(INTERNATIONAL_TOURNAMENTS) - set(found):
        print(f"[WARN] International league not currently available: {missing}")
    return found


def fetch_matches(league_id):
    """Collect all pages, including historical games for roster detection."""
    found = {}
    token = None
    seen = set()
    for _ in range(80):
        args = {"hl": "zh-CN", "leagueId": league_id}
        if token:
            args["pageToken"] = token
        data = api("getSchedule", args)
        schedule = data["data"].get("schedule")
        if not isinstance(schedule, dict) or not isinstance(schedule.get("events"), list):
            raise ScheduleError("malformed getSchedule response")
        for item in schedule["events"]:
            if item.get("type") != "match":
                continue
            match = item.get("match") or {}
            if match.get("id") and item.get("startTime"):
                found[str(match["id"])] = item
        next_token = (schedule.get("pages") or {}).get("newer")
        if not next_token or next_token in seen:
            break
        seen.add(next_token)
        token = next_token
    else:
        raise ScheduleError("schedule pagination exceeded 80 pages")
    return list(found.values())


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def identities(team):
    """Match by stable team ID, code, or full name; exclude TBD placeholders."""
    if not isinstance(team, dict):
        return set()
    keys = set()
    code = str(team.get("code") or "").strip().casefold()
    name = str(team.get("name") or "").strip().casefold()
    if code in PLACEHOLDERS and name in PLACEHOLDERS:
        return keys
    identifier = str(team.get("id") or "").strip()
    if identifier and identifier not in PLACEHOLDERS:
        keys.add("id:" + identifier)
    if code not in PLACEHOLDERS:
        keys.add("code:" + code)
    if name not in PLACEHOLDERS:
        keys.add("name:" + name)
    return keys


def roster_from_events(events, now=None):
    """LPL team identities for the current season (falls back to last year)."""
    now = now or datetime.now(timezone.utc)
    selected = []
    for year in (now.year, now.year - 1):
        selected = []
        for e in events:
            try:
                if dt(e["startTime"]).year == year:
                    selected.append(e)
            except (KeyError, ValueError):
                continue
        if selected:
            break
    roster = set()
    for event in selected:
        for team in (event.get("match") or {}).get("teams") or []:
            roster.update(identities(team))
    if not roster:
        raise ScheduleError("No team identities from LPL schedule")
    return roster


def include(event, slug, roster):
    """Publish only international matches involving at least one LPL team."""
    if not is_international_slug(slug):
        return False
    teams = (event.get("match") or {}).get("teams") or []
    return any(identities(team) & roster for team in teams)


def clean(s):
    return (str(s).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Fold ICS text at <=75 UTF-8 octets; continuation starts with one space."""
    out = []
    chunk = ""
    for char in line:
        if len((chunk + char).encode("utf-8")) > 75:
            out.append(chunk)
            chunk = " " + char
        else:
            chunk += char
    out.append(chunk)
    return "\r\n".join(out)


def timestamp(t):
    return t.strftime("%Y%m%dT%H%M%SZ")


def render(rows, now=None):
    now = now or datetime.now(timezone.utc)
    earliest = now - timedelta(days=KEEP_DAYS)
    events = []
    for slug, e in rows:
        try:
            start = dt(e["startTime"])
        except (ValueError, KeyError):
            continue
        if start < earliest:
            continue
        match = e.get("match") or {}
        mid = match.get("id")
        if not mid:
            continue
        teams = match.get("teams") or []
        def name(t):
            return str(t.get("code") or t.get("name") or "待定").strip()
        labels = [name(t) for t in teams[:2]]
        # Keep titles short even after a match ends.
        title = " vs ".join(labels) if len(labels) == 2 else "待定"
        score = None
        if e.get("state") == "completed" and len(teams) >= 2:
            wins = [(t.get("result") or {}).get("gameWins") for t in teams[:2]]
            if all(v is not None for v in wins):
                score = f"{wins[0]}-{wins[1]}"
        try:
            best_of = int((match.get("strategy") or {}).get("count") or 0)
        except (ValueError, TypeError):
            best_of = 0
        duration = {1: 1, 2: 2, 3: 3, 5: 4.5}.get(best_of, 2)
        # Title is only "TEAM vs TEAM"; detailed event metadata stays inside description.
        league = str((e.get("league") or {}).get("name") or LABELS.get(slug, slug.upper()))
        block = str(e.get("blockName") or "")
        summary = title
        details = ["赛区: " + league]
        if block:
            details.append("阶段: " + block)
        if best_of:
            details.append(f"赛制: BO{best_of}")
        if score is not None:
            details.append("比分: " + score)
        if len(teams) >= 2:
            details.append("对阵: " + str(teams[0].get("name", "待定")) +
                           " vs " + str(teams[1].get("name", "待定")))
        lines = [
            "BEGIN:VEVENT",
            "UID:lolmatch-" + str(mid) + "@lpl-lck-calendar",
            "DTSTAMP:" + timestamp(start),
            "DTSTART:" + timestamp(start),
            "DTEND:" + timestamp(start + timedelta(hours=duration)),
            "SUMMARY:" + clean(summary),
            "DESCRIPTION:" + clean("\n".join(details)),
            "END:VEVENT",
        ]
        events.append((start, lines))
    events.sort(key=lambda item: item[0])
    all_lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN",
        "PRODID:-//LPL-LCK-Calendar//ZH-CN//", "METHOD:PUBLISH",
        "X-WR-CALNAME:LOL 国际赛 · LPL 战队", "X-WR-TIMEZONE:UTC",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    for _, lines in events:
        all_lines.extend(lines)
    all_lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in all_lines) + "\r\n", len(events)


def load_fallback_fixtures(path=None):
    """Load verified fallback fixtures; a broken file never breaks the run.

    The upstream schedule API sometimes publishes confirmed draw pairings
    hours after the draw itself. Fixtures in fallback_fixtures.json are
    maintainer-verified (each carries its source) and pass through the same
    include() filter as API events, so stale or non-qualifying entries are
    dropped automatically. Invalid entries are skipped with a warning.
    """
    path = Path(path) if path else FALLBACK_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        print(f"[WARN] Ignoring unreadable fallback fixtures file: {exc}")
        return []
    if not isinstance(raw, list):
        print("[WARN] Ignoring fallback fixtures file: expected a JSON list")
        return []
    fixtures = []
    for entry in raw:
        try:
            if not isinstance(entry, dict):
                raise ValueError("entry is not an object")
            slug = str(entry["tournament"]).strip().casefold()
            if not is_international_slug(slug):
                raise ValueError(f"not an international tournament: {slug}")
            start = dt(str(entry["startTime"]))
            teams = entry["teams"]
            if not isinstance(teams, list) or len(teams) != 2:
                raise ValueError("teams must be a list of two")
            clean_teams = []
            for team in teams:
                code = str(team.get("code") or "").strip()
                name = str(team.get("name") or "").strip()
                if code.casefold() in PLACEHOLDERS or name.casefold() in PLACEHOLDERS:
                    raise ValueError("placeholder team in fixture")
                clean_teams.append({"code": code, "name": name})
            stable_id = str(entry.get("id") or "").strip()
            if not stable_id:
                stable_id = "fallback-" + slug + "-" + \
                    clean_teams[0]["code"].lower() + "-" + clean_teams[1]["code"].lower()
            fixtures.append({
                "id": stable_id,
                "tournament": slug,
                "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "blockName": str(entry.get("blockName") or ""),
                "leagueName": str(entry.get("leagueName") or LABELS.get(slug, slug.upper())),
                "strategy": int(entry.get("strategy") or 1),
                "teams": clean_teams,
            })
        except (KeyError, ValueError, TypeError) as exc:
            print(f"[WARN] Skipping invalid fallback fixture {entry!r}: {exc}")
    return fixtures


def apply_fallback_fixtures(selected, roster, fixtures=None):
    """Backfill confirmed fixtures the upstream API has not published yet.

    Each fixture must pass the same filter as API events (international,
    at least one LPL team). If upstream already has the pairing
    (same tournament, same two team codes, start within one day), upstream
    data wins but keeps the fixture's stable ID so subscribers do not get a
    duplicate event when the API catches up.
    """
    if fixtures is None:
        fixtures = load_fallback_fixtures()
    for fixture in fixtures:
        event = {
            "type": "match",
            "state": "unstarted",
            "startTime": fixture["startTime"],
            "blockName": fixture["blockName"],
            "league": {"name": fixture["leagueName"]},
            "match": {
                "id": fixture["id"],
                "strategy": {"count": fixture["strategy"]},
                "teams": [dict(team) for team in fixture["teams"]],
            },
        }
        if not include(event, fixture["tournament"], roster):
            print(f"[WARN] Fallback fixture does not qualify, skipped: {fixture['id']}")
            continue
        pair = {team["code"].casefold() for team in fixture["teams"]}
        original = None
        for key, (slug, existing) in selected.items():
            if slug != fixture["tournament"]:
                continue
            try:
                within_day = abs((dt(existing["startTime"]) -
                                   dt(fixture["startTime"])).total_seconds()) < 86400
            except (KeyError, ValueError):
                continue
            if not within_day:
                continue
            codes = {str(t.get("code", "")).strip().casefold()
                     for t in (existing.get("match") or {}).get("teams") or []}
            if codes == pair:
                original = key
                break
        if original is not None:
            selected[original][1]["match"]["id"] = fixture["id"]
            continue
        selected[fixture["id"]] = (fixture["tournament"], event)


def run():
    ids = leagues()
    roster = roster_from_events(fetch_matches(ids[ROSTER_LEAGUE]))
    selected = {}
    for slug, identifier in ids.items():
        if slug == ROSTER_LEAGUE:
            continue
        for event in fetch_matches(identifier):
            mid = str((event.get("match") or {}).get("id") or "")
            if mid and include(event, slug, roster):
                selected[mid] = (slug, event)
    apply_fallback_fixtures(selected, roster)
    if not selected:
        raise ScheduleError("No matching games; refusing to overwrite calendar")
    text, count = render(selected.values())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        OUTPUT.write_text(text, encoding="utf-8", newline="")
    print(f"[OK] {count} international matches with LPL teams, "
          f"{len(roster)} LPL team identity keys")


if __name__ == "__main__":
    try:
        run()
    except (OSError, ValueError, KeyError, TypeError, ScheduleError) as ex:
        print("[ERROR] Update failed; previous published calendar is kept: " + str(ex), file=sys.stderr)
        sys.exit(1)
