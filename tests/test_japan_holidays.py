import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from japan_holidays import kind_of, render, parse_csv


class JapanNationalHolidayTests(unittest.TestCase):
    def setUp(self):
        self.sample = {
            date(2026, 5, 3): "憲法記念日",
            date(2026, 5, 4): "みどりの日",
            date(2026, 5, 5): "こどもの日",
            date(2026, 5, 6): "休日",
            date(2026, 9, 21): "敬老の日",
            date(2026, 9, 22): "休日",
            date(2026, 9, 23): "秋分の日",
            date(2027, 3, 21): "春分の日",
            date(2027, 3, 22): "休日",
        }

    def test_2026_substitute(self):
        self.assertEqual(kind_of(date(2026, 5, 6), self.sample), "substitute")

    def test_2026_citizens_holiday(self):
        self.assertEqual(kind_of(date(2026, 9, 22), self.sample), "citizens")

    def test_2027_equinox_substitute(self):
        self.assertEqual(kind_of(date(2027, 3, 22), self.sample), "substitute")

    def test_chinese_translation_and_stable_uid(self):
        tw = render(self.sample, "zh-tw")
        cn = render(self.sample, "zh-cn")
        self.assertIn("SUMMARY:國民休息日", tw)
        self.assertIn("SUMMARY:国民休息日", cn)
        self.assertIn("SUMMARY:補假", tw)
        self.assertIn("SUMMARY:补假", cn)
        self.assertIn("UID:jp-holiday-20260922@sakura20040627", tw)
        self.assertIn("DTSTART;VALUE=DATE:20260922", tw)
        self.assertIn("DTEND;VALUE=DATE:20260923", tw)
        self.assertEqual(tw.count("BEGIN:VEVENT"), len(self.sample))
        self.assertNotIn("ハロウィン", tw)
        self.assertTrue(all(len(x.encode("utf-8")) <= 75 for x in tw.split("\r\n")))


if __name__ == "__main__":
    unittest.main()
