import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import generate
from generate import (
    ScheduleError, apply_fallback_fixtures, identities, include,
    is_international_slug, load_fallback_fixtures, render, roster_from_events,
)

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
        # The roster is derived from the current season's LPL league schedule.
        lpl_domestic = [
            match("r1", "Bilibili Gaming", "BLG", "200", "Top Esports", "TES", "201"),
            match("r2", "JD Gaming", "JDG", "202", "Weibo Gaming", "WBG", "203"),
            match("r3", "Invictus Gaming", "IG", "204", "Team WE", "WE", "205"),
            match("r4", "Anyone's Legend", "AL", "900", "Royal Never Give Up", "RNG", "206"),
        ]
        self.roster = roster_from_events(lpl_domestic, NOW)

    # 1-4: an LPL team in any international tournament is kept.
    def test_lpl_team_at_worlds_is_kept(self):
        e = match("w1", "Bilibili Gaming", "BLG", "200", "T1", "T1", "101")
        self.assertTrue(include(e, "worlds", self.roster))

    def test_lpl_team_at_msi_is_kept(self):
        e = match("m1", "Top Esports", "TES", "201", "Gen.G", "GEN", "100")
        self.assertTrue(include(e, "msi", self.roster))

    def test_lpl_team_at_first_stand_is_kept(self):
        e = match("f1", "JD Gaming", "JDG", "202", "G2 Esports", "G2", "300")
        self.assertTrue(include(e, "first_stand", self.roster))

    def test_lpl_team_at_ewc_is_kept(self):
        e = match("e1", "Weibo Gaming", "WBG", "203", "Dplus KIA", "DK", "102")
        self.assertTrue(include(e, "ewc_lol", self.roster))

    def test_all_lpl_international_is_kept(self):
        e = match("w2", "Bilibili Gaming", "BLG", "200", "Top Esports", "TES", "201")
        self.assertTrue(include(e, "worlds", self.roster))

    # 5-7: regional leagues are never kept, whoever plays.
    def test_lpl_domestic_league_is_excluded(self):
        e = match("d1", "Bilibili Gaming", "BLG", "200", "Top Esports", "TES", "201")
        self.assertFalse(include(e, "lpl", self.roster))

    def test_lck_domestic_league_is_excluded(self):
        e = match("d2", "Gen.G", "GEN", "100", "T1", "T1", "101")
        self.assertFalse(include(e, "lck", self.roster))

    def test_g2_domestic_league_is_excluded(self):
        e = match("d3", "G2 Esports", "G2", "300", "Fnatic", "FNC", "301")
        self.assertFalse(include(e, "lec", self.roster))

    def test_demacia_cup_is_a_domestic_cup_and_excluded(self):
        e = match("d4", "Bilibili Gaming", "BLG", "200", "Top Esports", "TES", "201")
        self.assertFalse(include(e, "demacia_cup", self.roster))

    # 8: an international match without an LPL team is excluded.
    def test_worlds_without_lpl_team_is_excluded(self):
        e = match("w3", "T1", "T1", "101", "Gen.G", "GEN", "100")
        self.assertFalse(include(e, "worlds", self.roster))
        e2 = match("w4", "G2 Esports", "G2", "300", "Fnatic", "FNC", "301")
        self.assertFalse(include(e2, "worlds", self.roster))

    # 9: AL is a regular LPL team now (rule changed 2026-10-24): its
    # international matches are kept like any other LPL team's.
    def test_al_matches_are_kept_like_any_lpl_team(self):
        vs_foreign = match("a1", "Anyone's Legend", "AL", "900", "T1", "T1", "101")
        self.assertTrue(include(vs_foreign, "worlds", self.roster))
        vs_lpl = match("a2", "Anyone's Legend", "AL", "900",
                       "Bilibili Gaming", "BLG", "200")
        self.assertTrue(include(vs_lpl, "worlds", self.roster))
        at_msi = match("a3", "Top Esports", "TES", "201",
                       "Anyone's Legend", "AL", "900")
        self.assertTrue(include(at_msi, "msi", self.roster))

    def test_tbd_match_never_qualifies(self):
        self.assertEqual(identities({"code": "TBD", "name": "TBD", "id": "100"}), set())
        e = match("t1", "TBD", "TBD", "", "TBD", "TBD", "")
        self.assertFalse(include(e, "worlds", self.roster))

    def test_international_slug_detection(self):
        for slug in ("worlds", "msi", "first_stand", "ewc_lol", "ewc_lol_2027"):
            self.assertTrue(is_international_slug(slug), slug)
        for slug in ("lpl", "lck", "lec", "lcs", "demacia_cup", "kespa_cup",
                     "wqs", "lcp", "asian_games"):
            self.assertFalse(is_international_slug(slug), slug)

    # 10: the same match from two sources must not duplicate.
    def test_fallback_does_not_duplicate_late_api_event(self):
        upstream = match("api123", "Team Secret Whales", "TSW", "400",
                         "Invictus Gaming", "IG", "204", "2026-10-24T21:00:00Z")
        selected = {"api123": ("worlds", upstream)}
        fixtures = [{
            "id": "worlds-2026-r2-tsw-ig", "tournament": "worlds",
            "startTime": "2026-10-24T21:00:00Z", "blockName": "瑞士轮·第二轮",
            "leagueName": "Worlds", "strategy": 1,
            "teams": [{"code": "TSW", "name": "Team Secret Whales"},
                      {"code": "IG", "name": "Invictus Gaming"}],
        }]
        apply_fallback_fixtures(selected, self.roster, fixtures)
        self.assertEqual(len(selected), 1)
        # Upstream data wins, but the stable fallback UID is kept.
        self.assertEqual(upstream["match"]["id"], "worlds-2026-r2-tsw-ig")
        result, count = render(selected.values(), NOW)
        self.assertEqual(count, 1)
        self.assertEqual(result.count("SUMMARY:TSW vs IG"), 1)

    def test_shipped_fallback_fixtures_only_contain_qualified_matches(self):
        fixtures = load_fallback_fixtures()
        self.assertTrue(fixtures)
        selected = {}
        apply_fallback_fixtures(selected, self.roster, fixtures)
        result, count = render(selected.values(), NOW)
        self.assertEqual(count, len(fixtures))
        self.assertIn("SUMMARY:TSW vs IG", result)
        self.assertIn("SUMMARY:TLAW vs BLG", result)
        for banned in ("G2 vs LOS", "GEN vs HLE", "T1 vs DK"):
            self.assertNotIn("SUMMARY:" + banned, result)

    def test_fallback_fixture_without_lpl_team_is_skipped(self):
        fixtures = [
            {"id": "bad-nolpl", "tournament": "worlds",
             "startTime": "2026-10-24T20:00:00Z", "blockName": "",
             "leagueName": "Worlds", "strategy": 1,
             "teams": [{"code": "T1", "name": "T1"},
                       {"code": "GEN", "name": "Gen.G"}]},
        ]
        selected = {}
        apply_fallback_fixtures(selected, self.roster, fixtures)
        self.assertEqual(selected, {})

    def test_fallback_fixture_with_al_is_kept(self):
        fixtures = [
            {"id": "ok-al", "tournament": "worlds",
             "startTime": "2026-10-24T20:00:00Z", "blockName": "",
             "leagueName": "Worlds", "strategy": 1,
             "teams": [{"code": "AL", "name": "Anyone's Legend"},
                       {"code": "T1", "name": "T1"}]},
        ]
        selected = {}
        apply_fallback_fixtures(selected, self.roster, fixtures)
        self.assertEqual(len(selected), 1)

    # 11: an upstream API failure must never empty the published calendar.
    def test_api_failure_keeps_previous_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "calendar.ics"
            target.write_text("PREVIOUS CALENDAR", encoding="utf-8")
            with mock.patch.object(generate, "OUTPUT", target), \
                    mock.patch.object(generate, "api",
                                      side_effect=ScheduleError("API down")):
                with self.assertRaises(ScheduleError):
                    generate.run()
            self.assertEqual(target.read_text(encoding="utf-8"), "PREVIOUS CALENDAR")

    # 12: a changed start time or score updates the same event (stable UID).
    def test_updated_time_and_score_keep_same_uid(self):
        before = match("u1", "Gen.G", "GEN", "100", "Top Esports", "TES", "201",
                       "2026-10-24T12:00:00Z")
        first, _ = render([("worlds", before)], NOW)
        after = match("u1", "Gen.G", "GEN", "100", "Top Esports", "TES", "201",
                      "2026-10-24T15:00:00Z")
        after["state"] = "completed"
        after["match"]["teams"][0]["result"] = {"gameWins": 1}
        after["match"]["teams"][1]["result"] = {"gameWins": 3}
        second, _ = render([("worlds", after)], NOW)
        self.assertIn("UID:lolmatch-u1@lpl-lck-calendar", first)
        self.assertIn("UID:lolmatch-u1@lpl-lck-calendar", second)
        self.assertIn("DTSTART:20261024T150000Z", second)
        self.assertIn("比分: 1-3", second)

    def test_completed_match_follows_intl_score_format(self):
        e = match("done", "Gen.G", "GEN", "100", "Top Esports", "TES", "201")
        e["state"] = "completed"
        e["match"]["teams"][0]["result"] = {"gameWins": 3}
        e["match"]["teams"][1]["result"] = {"gameWins": 1}
        result, _ = render([("worlds", e)], NOW)
        self.assertIn("SUMMARY:GEN vs TES", result)
        self.assertIn("比分: 3-1", result)

    def test_ics_can_be_imported_and_lines_fit_rfc(self):
        e = match("i1", "Bilibili Gaming", "BLG", "200", "T1", "T1", "101")
        result, count = render([("worlds", e)], NOW)
        self.assertEqual(count, 1)
        self.assertIn("DTSTART:20261024T120000Z", result)
        self.assertIn("SUMMARY:BLG vs T1", result)
        self.assertNotIn("SUMMARY:Worlds:", result)
        self.assertIn("赛区: 全球总决赛", result)
        self.assertIn("赛制: BO3", result)
        self.assertIn("UID:lolmatch-i1@lpl-lck-calendar", result)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75
                            for line in result.split("\r\n") if line))


if __name__ == "__main__":
    unittest.main()
