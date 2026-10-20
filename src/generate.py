#!/usr/bin/env python3
"""LPL/LCK + G2 team-filtered iCalendar, excluding AL."""
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
API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"  # public site key
BASE_URLS = (
    "https://esports-api.lolesports.com/persisted/gw",
    "https://prod-relapi.ewp.gg/persisted/gw",
)
REGIONS = ("lpl", "lck")
EXCLUDED_TEAM_CODES = {"al"}
EXCLUDED_TEAM_NAMES = {"anyone's legend", "anyones legend", "anyone’s legend"}
ADDED_TEAM_CODES = {"g2"}
ADDED_TEAM_NAMES = {"g2 esports"}
INTERNATIONAL = ("msi", "worlds", "first_stand", "ewc_lol", "demacia_cup")
ALL = REGIONS + ("lec",) + INTERNATIONAL
LABELS = {
    "lpl": "LPL", "lck": "LCK", "lec": "LEC", "msi": "季中冠军赛",
    "worlds": "全球总决赛", "first_stand": "全球先锋赛",
    "ewc_lol": "电竞世界杯", "demacia_cup": "德玛西亚杯",
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


def leagues():
    data = api("getLeagues", {"hl": "zh-CN"})
    items = data["data"].get("leagues")
    if not isinstance(items, list):
        raise ScheduleError("missing leagues in API response")
    found = {str(x.get("slug")): str(x["id"]) for x in items
             if isinstance(x, dict) and x.get("slug") in ALL and x.get("id")}
    if not all(region in found for region in REGIONS + ("lec",)):
        raise ScheduleError("LPL/LCK/LEC league IDs missing; refusing to publish")
    for missing in set(ALL) - set(found):
        print(f"[WARN] League not currently available: {missing}")
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
        raise ScheduleError("No team identities from LPL/LCK schedule")
    return roster


def is_excluded(team):
    """Always exclude AL, even if the opponent belongs to a selected region."""
    if not isinstance(team, dict):
        return False
    code = str(team.get("code") or "").strip().casefold()
    name = str(team.get("name") or "").strip().casefold()
    return code in EXCLUDED_TEAM_CODES or name in EXCLUDED_TEAM_NAMES


def is_added(team):
    """Include G2 even in games with no LPL/LCK opponent."""
    if not isinstance(team, dict):
        return False
    code = str(team.get("code") or "").strip().casefold()
    name = str(team.get("name") or "").strip().casefold()
    return code in ADDED_TEAM_CODES or name in ADDED_TEAM_NAMES


def include(event, slug, roster):
    teams = (event.get("match") or {}).get("teams") or []
    if any(is_excluded(team) for team in teams):
        return False
    if slug in REGIONS:
        return True
    return any(is_added(team) or identities(team) & roster for team in teams)


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
        "X-WR-CALNAME:LOL 赛程 · LPL/LCK/G2 (不含 AL)", "X-WR-TIMEZONE:UTC",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    for _, lines in events:
        all_lines.extend(lines)
    all_lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in all_lines) + "\r\n", len(events)


def run():
    ids = leagues()
    source = {slug: fetch_matches(identifier) for slug, identifier in ids.items()}
    region_events = source["lpl"] + source["lck"]
    roster = roster_from_events(region_events)
    selected = {}
    for slug in ALL:
        for event in source.get(slug, []):
            mid = str((event.get("match") or {}).get("id") or "")
            if mid and include(event, slug, roster):
                selected[mid] = (slug, event)
    if not selected:
        raise ScheduleError("No matching games; refusing to overwrite calendar")
    text, count = render(selected.values())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        OUTPUT.write_text(text, encoding="utf-8", newline="")
    print(f"[OK] {count} matches (LPL/LCK + G2, AL excluded), {len(roster)} team identity keys")


if __name__ == "__main__":
    try:
        run()
    except (OSError, ValueError, KeyError, TypeError, ScheduleError) as ex:
        print("[ERROR] Update failed; previous published calendar is kept: " + str(ex), file=sys.stderr)
        sys.exit(1)
