#!/usr/bin/env python3
"""Translate Cabinet Office (内閣府) official national holidays into Chinese ICS.

Source: https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv
Only officially announced dates are published; future equinox dates are not guessed.
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SOURCE = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
BASE = Path(__file__).resolve().parent.parent / "public"
FIRST_YEAR = 2026

NAMES = {
    "元日": ("元旦", "元旦"),
    "成人の日": ("成人之日", "成人节"),
    "建国記念の日": ("建國紀念日", "建国纪念日"),
    "天皇誕生日": ("天皇誕辰", "天皇诞辰"),
    "春分の日": ("春分日", "春分日"),
    "昭和の日": ("昭和之日", "昭和之日"),
    "憲法記念日": ("憲法紀念日", "宪法纪念日"),
    "みどりの日": ("綠之日", "绿之日"),
    "こどもの日": ("兒童節", "儿童节"),
    "海の日": ("海之日", "海之日"),
    "山の日": ("山之日", "山之日"),
    "敬老の日": ("敬老日", "敬老日"),
    "秋分の日": ("秋分日", "秋分日"),
    "スポーツの日": ("體育日", "体育日"),
    "文化の日": ("文化日", "文化日"),
    "勤労感謝の日": ("勤勞感謝日", "勤劳感谢日"),
    "substitute": ("補假", "补假"),
    "citizens": ("國民休息日", "国民休息日"),
}


def load_official_csv() -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                SOURCE, headers={"User-Agent": "Mozilla/5.0 (Japan-Holidays-Calendar)"}
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                data = response.read()
            if len(data) < 2000:
                raise ValueError("Unexpectedly small official CSV")
            return data
        except (OSError, ValueError) as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"Cabinet Office data unavailable: {last_error}")


def parse_csv(data: bytes) -> dict[date, str]:
    holidays = {}
    for row in csv.reader(io.StringIO(data.decode("cp932"))):
        if len(row) < 2:
            continue
        parts = row[0].strip().split("/")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            continue
        day = date(*map(int, parts))
        if day.year < FIRST_YEAR:
            continue
        name = row[1].strip()
        if name not in NAMES and name != "休日":
            raise ValueError("Untranslated Japanese holiday: " + name)
        if day in holidays and holidays[day] != name:
            raise ValueError(f"Conflicting official rows for {day}")
        holidays[day] = name
    if len(holidays) < 32 or min(d.year for d in holidays) != FIRST_YEAR:
        raise ValueError("Missing official holiday dates; old file preserved")
    if max(d.year for d in holidays) < datetime.now(timezone.utc).year:
        raise ValueError("The CSV does not cover the current year")
    return holidays


def kind_of(day: date, holidays: dict[date, str]) -> str:
    if holidays[day] != "休日":
        return "national"
    prev = holidays.get(day - timedelta(days=1))
    nxt = holidays.get(day + timedelta(days=1))
    if prev and prev != "休日" and nxt and nxt != "休日":
        return "citizens"
    cursor = day - timedelta(days=1)
    for _ in range(10):
        label = holidays.get(cursor)
        if not label:
            break
        if cursor.weekday() == 6 and label != "休日":
            return "substitute"
        cursor -= timedelta(days=1)
    raise ValueError(f"Unrecognized official 休日: {day}")


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(value: str) -> str:
    if len(value.encode("utf-8")) <= 75:
        return value
    output, chunk = [], ""
    for character in value:
        if len((chunk + character).encode("utf-8")) > 75:
            output.append(chunk)
            chunk = " " + character
        else:
            chunk += character
    output.append(chunk)
    return "\r\n".join(output)


def render(holidays: dict[date, str], locale: str) -> str:
    if locale not in ("zh-tw", "zh-cn"):
        raise ValueError("Unsupported locale")
    n = 0 if locale == "zh-tw" else 1
    calendar_name = "日本國定假日・繁體中文" if n == 0 else "日本法定节假日・简体中文"
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN",
        f"PRODID:-//Kaikou Japan National Holidays//{locale.upper()}//",
        "METHOD:PUBLISH", "X-WR-CALNAME:" + calendar_name,
        "X-WR-TIMEZONE:Asia/Tokyo",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
    ]
    for day in sorted(holidays):
        ja = holidays[day]
        kind = kind_of(day, holidays)
        title = NAMES[ja if kind == "national" else kind][n]
        japanese = ja if kind == "national" else ("国民の休日" if kind == "citizens" else "振替休日")
        category = (("國定假日", "法定节假日") if kind == "national"
                    else (("國民休息日", "国民休息日") if kind == "citizens"
                          else ("補假", "补假")))[n]
        desc = f"{'原文' if n == 0 else '日文'}：{japanese}；{'類別' if n == 0 else '类别'}：{category}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:jp-holiday-{day:%Y%m%d}@sakura20040627",
            "DTSTAMP:20261021T000000Z",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + escape(title),
            "DESCRIPTION:" + escape(desc),
            "TRANSP:TRANSPARENT", "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    calendar = "\r\n".join(fold(line) for line in lines) + "\r\n"
    if any(len(line.encode("utf-8")) > 75 for line in calendar.split("\r\n")):
        raise ValueError("Invalid RFC 5545 line")
    return calendar


def main() -> None:
    holidays = parse_csv(load_official_csv())
    if sum(x.year == 2026 for x in holidays) != 18:
        raise ValueError("Unexpected 2026 Cabinet Office holiday count")
    if sum(x.year == 2027 for x in holidays) != 17:
        raise ValueError("Unexpected 2027 Cabinet Office holiday count")
    outputs = {locale: render(holidays, locale) for locale in ("zh-tw", "zh-cn")}
    for locale, data in outputs.items():
        path = BASE / f"japan-public-holidays-{locale}.ics"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != data:
            path.write_bytes(data.encode("utf-8"))
            print(f"Updated {locale}, events: {len(holidays)}")
        else:
            print(f"No change: {locale}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] Old subscriptions preserved: {exc}", file=sys.stderr)
        sys.exit(1)
