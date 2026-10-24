import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from generate import identities, roster_from_events, include, render, apply_known_worlds_round2

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

    def test_g2_international_is_kept_without_lpl_lck(self):
        e = match("i2", "G2 Esports", "G2", "300", "Fnatic", "FNC", "301")
        self.assertTrue(include(e, "worlds", self.roster))

    def test_g2_lec_matches_only(self):
        g2 = match("e1", "G2 Esports", "G2", "300", "Fnatic", "FNC", "301")
        other = match("e2", "Fnatic", "FNC", "301", "Karmine Corp", "KC", "302")
        self.assertTrue(include(g2, "lec", self.roster))
        self.assertFalse(include(other, "lec", self.roster))

    def test_foreign_only_international_is_excluded(self):
        e = match("i4", "Cloud9", "C9", "302", "Fnatic", "FNC", "301")
        self.assertFalse(include(e, "worlds", self.roster))

    def test_al_own_lpl_game_is_excluded(self):
        e = match("r9", "Anyone's Legend", "AL", "900", "Bilibili Gaming", "BLG", "200")
        self.assertFalse(include(e, "lpl", self.roster))

    def test_al_vs_lck_or_g2_is_excluded(self):
        e = match("i9", "Anyone's Legend", "AL", "900", "G2 Esports", "G2", "300")
        self.assertFalse(include(e, "worlds", self.roster))
        e2 = match("i10", "Gen.G", "GEN", "100", "Anyone's Legend", "AL", "900")
        self.assertFalse(include(e2, "msi", self.roster))

    def test_g2_full_name_fallback_is_kept(self):
        e = match("i5", "G2 Esports", "TBD", "300", "Cloud9", "C9", "302")
        self.assertTrue(include(e, "worlds", self.roster))

    def test_all_regional_matches_are_kept(self):
        e = match("r3", "TBD", "TBD", "", "TBD", "TBD", "")
        self.assertTrue(include(e, "lpl", self.roster))

    def test_tbd_ids_never_match(self):
        self.assertEqual(identities({"code": "TBD", "name": "TBD", "id": "100"}), set())
        e = match("i3", "TBD", "TBD", "100", "TBD", "TBD", "200")
        self.assertFalse(include(e, "msi", self.roster))

    def test_completed_match_follows_intl_score_format(self):
        e = match("done", "Gen.G", "GEN", "100", "Top Esports", "TES", "201")
        e["state"] = "completed"
        e["match"]["teams"][0]["result"] = {"gameWins": 3}
        e["match"]["teams"][1]["result"] = {"gameWins": 1}
        result, _ = render([("worlds", e)], NOW)
        self.assertIn("SUMMARY:GEN vs TES", result)
        self.assertIn("比分: 3-1", result)

    def test_ics_can_be_imported_and_lines_fit_rfc(self):
        e = match("i1", "G2 Esports", "G2", "300", "Gen.G", "GEN", "100")
        result, count = render([("worlds", e)], NOW)
        self.assertEqual(count, 1)
        self.assertIn("DTSTART:20261024T120000Z", result)
        self.assertIn("SUMMARY:G2 vs GEN", result)
        self.assertNotIn("SUMMARY:Worlds:", result)
        self.assertIn("赛区: 全球总决赛", result)
        self.assertIn("赛制: BO3", result)
        self.assertIn("UID:lolmatch-i1@lpl-lck-calendar", result)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in result.split("\r\n") if line))


    def test_worlds_2026_round_two_fallback_keeps_only_qualified_games(self):
        selected = {}
        apply_known_worlds_round2(selected)
        result, count = render(selected.values(), NOW)
        self.assertEqual(count, 5)
        self.assertIn("SUMMARY:G2 vs LOS", result)
        self.assertIn("SUMMARY:TSW vs IG", result)
        self.assertIn("SUMMARY:GEN vs HLE", result)
        self.assertIn("SUMMARY:T1 vs DK", result)
        self.assertIn("SUMMARY:TLAW vs BLG", result)
        self.assertIn("DTSTART:20261024T190000Z", result)
        self.assertNotIn("SUMMARY:AL vs TES", result)
        self.assertNotIn("SUMMARY:CFO vs MKOI", result)

    def test_worlds_round_two_late_api_event_does_not_duplicate(self):
        upstream = match("api123", "G2 Esports", "G2", "2",
                         "LOS", "LOS", "3", "2026-10-24T19:00:00Z")
        selected = {"api123": ("worlds", upstream)}
        apply_known_worlds_round2(selected)
        result, count = render(selected.values(), NOW)
        self.assertEqual(count, 5)
        self.assertEqual(upstream["match"]["id"], "worlds-2026-r2-g2-los")
        self.assertEqual(result.count("SUMMARY:G2 vs LOS"), 1)


if __name__ == "__main__":
    unittest.main()
