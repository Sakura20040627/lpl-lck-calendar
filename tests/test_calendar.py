import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from generate import identities, roster_from_events, include, render

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
WHEN = "2026-10-24T12:00:00Z"


def match(mid, a, ac, aid, b, bc, bid, when=WHEN):
    return {
        "type": "match", "state": "unstarted", "startTime": when,
        "match": {"id": mid, "strategy": {"count": 3}, "teams": [
            {"name": a, "code": ac, "id": aid},
            {"name": b, "code": bc, "id": bid},
        ]},
    }


class CalendarTests(unittest.TestCase):
    def setUp(self):
        domestic = [
            match("r1", "Gen.G", "GEN", "100", "T1", "T1", "101"),
            match("r2", "Bilibili Gaming", "BLG", "200", "Top Esports", "TES", "201"),
        ]
        self.roster = roster_from_events(domestic, NOW)

    def test_lck_team_in_international_is_kept(self):
        e = match("i1", "G2 Esports", "G2", "300", "Gen.G", "GEN", "100")
        self.assertTrue(include(e, "worlds", self.roster))

    def test_foreign_only_international_is_excluded(self):
        e = match("i2", "G2 Esports", "G2", "300", "Fnatic", "FNC", "301")
        self.assertFalse(include(e, "worlds", self.roster))

    def test_all_regional_matches_are_kept(self):
        e = match("r3", "TBD", "TBD", "", "TBD", "TBD", "")
        self.assertTrue(include(e, "lpl", self.roster))

    def test_tbd_ids_never_match(self):
        self.assertEqual(identities({"code": "TBD", "name": "TBD", "id": "100"}), set())
        e = match("i3", "TBD", "TBD", "100", "TBD", "TBD", "200")
        self.assertFalse(include(e, "msi", self.roster))

    def test_ics_can_be_imported_and_lines_fit_rfc(self):
        e = match("i1", "G2 Esports", "G2", "300", "Gen.G", "GEN", "100")
        result, count = render([("worlds", e)], NOW)
        self.assertEqual(count, 1)
        self.assertIn("DTSTART:20261024T120000Z", result)
        self.assertIn("全球总决赛", result)
        self.assertIn("UID:lolmatch-i1@lpl-lck-calendar", result)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in result.split("\r\n") if line))


if __name__ == "__main__":
    unittest.main()
