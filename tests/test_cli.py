import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import UTC, date, datetime
from unittest.mock import patch

from simulcast_calendar import CalendarBlockedError, Locale, ReleaseCalendarDay, ReleaseCalendarItem, ReleaseCalendarWeek
from simulcast_calendar.cli import main


def sample_week() -> ReleaseCalendarWeek:
    release = ReleaseCalendarItem(
        series_id="GY8VEQ95Y",
        episode_id="GE00374943ENUS",
        season_title="Series (English)",
        episode_title="Episode title",
        episode_number=1,
        release_time=datetime(2026, 10, 20, 12, 30, tzinfo=UTC),
        premium=True,
        thumbnail_url="https://img.example/episode.jpg",
        audio_locale="en-US",
        audio_label="English",
    )
    days = tuple(
        ReleaseCalendarDay(date(2026, 10, 19 + index), (release,) if index == 1 else ())
        for index in range(7)
    )
    return ReleaseCalendarWeek(date(2026, 10, 19), days, Locale.PT_BR)


class CliTests(unittest.TestCase):
    @patch("simulcast_calendar.cli.CalendarClient")
    def test_cli_passes_options_and_prints_original_title(self, client_class) -> None:
        week = sample_week()
        client_class.return_value.__enter__.return_value.get_week.return_value = week
        output = io.StringIO()

        with redirect_stdout(output):
            result = main([
                "--locale", "pt-br", "--date", "2026-10-20",
                "--proxy", "http://localhost:8080", "--user-agent", "test-agent", "--timeout", "7.5",
            ])

        self.assertEqual(result, 0)
        client_class.assert_called_once_with(
            Locale.PT_BR,
            user_agent="test-agent",
            proxy="http://localhost:8080",
            timeout=7.5,
        )
        client_class.return_value.__enter__.return_value.get_week.assert_called_once_with(date(2026, 10, 20))
        self.assertIn("Series (English)", output.getvalue())
        self.assertIn("Audio: English (US)", output.getvalue())
        self.assertIn("Week: 2026-10-19 – 2026-10-25", output.getvalue())
        self.assertIn("Episode 1: Episode title", output.getvalue())

    @patch("simulcast_calendar.cli.CalendarClient")
    def test_cli_can_print_only_the_selected_day(self, client_class) -> None:
        week = sample_week()
        client = client_class.return_value.__enter__.return_value
        client.locale = Locale.PT_BR
        client.get_day.return_value = week.days[1]
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["--day", "--date", "2026-10-20"])

        self.assertEqual(result, 0)
        client.get_day.assert_called_once_with(date(2026, 10, 20))
        client.get_week.assert_not_called()
        self.assertIn("Date: 2026-10-20", output.getvalue())
        self.assertNotIn("Week:", output.getvalue())

    @patch("simulcast_calendar.cli.CalendarClient")
    def test_cli_groups_audio_variants(self, client_class) -> None:
        week = sample_week()
        item = week.days[1].releases[0]
        alternate = replace(item, episode_id="GE00374943TLPH", audio_locale="tl-PH", audio_label="Tagalog")
        days = list(week.days)
        days[1] = replace(days[1], releases=(item, alternate))
        client_class.return_value.__enter__.return_value.get_week.return_value = replace(week, days=tuple(days))
        output = io.StringIO()

        with redirect_stdout(output):
            result = main(["--group-dubs"])

        self.assertEqual(result, 0)
        self.assertIn("GE00374943  ·  2 versions", output.getvalue())
        self.assertIn("English (US)", output.getvalue())
        self.assertIn("Filipino", output.getvalue())
        self.assertIn("2026-10-20  12:30 UTC", output.getvalue())

    @patch("simulcast_calendar.cli.CalendarClient")
    def test_cli_reports_calendar_errors_with_nonzero_status(self, client_class) -> None:
        client_class.return_value.__enter__.return_value.get_week.side_effect = CalendarBlockedError("blocked")
        error_output = io.StringIO()

        with redirect_stderr(error_output):
            result = main([])

        self.assertEqual(result, 1)
        self.assertIn("CalendarBlockedError: blocked", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
