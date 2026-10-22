import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from simulcast_calendar import (
    CalendarBlockedError,
    CalendarClient,
    CalendarError,
    CalendarRequestError,
    Locale,
)
from simulcast_calendar.client import _calendar_url, _check_response, _parse_week
from simulcast_calendar.locales import audio_language_name, audio_label_from_title, audio_locale_for_episode_id


HTML = (Path(__file__).parent / "fixtures" / "calendar_week.html").read_text(encoding="utf-8")


def response(status: int, headers: dict[str, str] | None = None, body: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status,
        headers=headers or {},
        text=body,
        url="https://www.crunchyroll.com/simulcastcalendar",
    )


class LocaleTests(unittest.TestCase):
    def test_locale_routes(self) -> None:
        routes = {
            Locale.EN_US: "",
            Locale.ES_419: "/es",
            Locale.ES_ES: "/es-es",
            Locale.PT_BR: "/pt-br",
            Locale.PT_PT: "/pt-pt",
            Locale.FR_FR: "/fr",
            Locale.DE_DE: "/de",
            Locale.AR: "/ar",
            Locale.IT_IT: "/it",
            Locale.RU_RU: "/ru",
            Locale.HI_IN: "/hi",
            Locale.PL_PL: "/pl",
            Locale.ZH_TW: "/zh-tw",
            Locale.TH_TH: "/th",
            Locale.TL_PH: "/tl-ph",
            Locale.ID_ID: "/id",
            Locale.KO_KR: "/ko",
        }
        for locale, path in routes.items():
            with self.subTest(locale=locale):
                self.assertIn(f"{path}/simulcastcalendar?", _calendar_url(locale, date(2026, 10, 20)))

    def test_url_encodes_selected_date(self) -> None:
        self.assertTrue(_calendar_url(Locale.PT_BR, date(2026, 10, 20)).endswith("date=2026-10-20"))

    def test_audio_locale_suffix(self) -> None:
        locale = audio_locale_for_episode_id("GE00380778ES419")
        self.assertEqual(locale, "es-419")
        self.assertEqual(audio_language_name(locale), "Spanish (Latin America)")
        self.assertIsNone(audio_locale_for_episode_id("GE00000000ZZZZ"))

    def test_audio_label_is_read_without_changing_title(self) -> None:
        self.assertEqual(audio_label_from_title("PSYREN Season 1 (English)"), "English")
        self.assertIsNone(audio_label_from_title("Series (Season 1)"))


class ParserTests(unittest.TestCase):
    def test_parses_captured_live_calendar_fixture(self) -> None:
        html = (Path(__file__).parent / "fixtures" / "calendar_week_live.html").read_text(encoding="utf-8")
        week = _parse_week(html, date(2026, 10, 19), Locale.EN_US)
        self.assertEqual(len(week.days), 7)
        self.assertEqual([len(day.releases) for day in week.days], [16, 10, 14, 0, 0, 0, 0])
        releases = [release for day in week.days for release in day.releases]
        self.assertTrue(all(release.release_time.tzinfo for release in releases))
        self.assertTrue(all(type(release.premium) is bool and release.premium for release in releases))
        self.assertEqual([day.date for day in week.days if not day.releases], [
            date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24), date(2026, 10, 25),
        ])
        psyren = next(release for release in releases if release.season_title == "PSYREN Season 1 (English)")
        self.assertEqual((psyren.audio_label, psyren.audio_locale), ("English", "en-US"))

    def test_parses_week_and_release_fields(self) -> None:
        week = _parse_week(HTML, date(2026, 10, 19), Locale.KO_KR)
        self.assertEqual(len(week.days), 7)
        self.assertEqual(week.days[1].date, date(2026, 10, 20))
        item = week.days[1].releases[0]
        self.assertEqual((item.series_id, item.episode_id), ("GY8VEQ95Y", "GE00374943ENUS"))
        self.assertEqual((item.season_title, item.episode_title), ("Series (English)", "Episode title"))
        self.assertEqual((item.audio_locale, item.audio_language), ("en-US", "English (US)"))
        self.assertEqual(item.audio_label, "English")
        self.assertEqual(item.episode_number, 2.5)
        self.assertEqual(item.release_time, datetime(2026, 10, 20, 10, 30, tzinfo=UTC))
        self.assertTrue(item.premium)
        self.assertEqual(item.thumbnail_url, "https://img.example/episode.jpg")
        self.assertEqual(len(week.on(date(2026, 10, 20))), 2)

    def test_free_release_is_a_boolean_false(self) -> None:
        html = HTML.replace('<svg class="premium-flag"></svg>', "", 1)
        week = _parse_week(html, date(2026, 10, 19), Locale.EN_US)
        self.assertIs(week.days[1].releases[0].premium, False)

    def test_groups_audio_variants_by_episode_id(self) -> None:
        week = _parse_week(HTML, date(2026, 10, 19), Locale.KO_KR)
        groups = week.grouped_releases()
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].releases), 2)
        self.assertEqual(groups[0].episode_id, "GE00374943")
        self.assertEqual(groups[0].audio_languages, ("English (US)", "Spanish (Latin America)"))

    def test_rejects_unexpected_week_shape(self) -> None:
        with self.assertRaisesRegex(CalendarError, "expected 7 calendar days"):
            _parse_week('<ol class="days"><li class="day"></li></ol>', date(2026, 10, 19), Locale.EN_US)

    def test_rejects_naive_release_time(self) -> None:
        html = HTML.replace("2026-10-20T12:30:00+02:00", "2026-10-20T12:30:00")
        with self.assertRaisesRegex(CalendarError, "invalid episode date"):
            _parse_week(html, date(2026, 10, 19), Locale.EN_US)


class ResponseTests(unittest.TestCase):
    def test_identifies_cloudflare_browser_challenge(self) -> None:
        with self.assertRaisesRegex(CalendarBlockedError, "cf-mitigated: challenge"):
            _check_response(response(403, {"cf-mitigated": "challenge", "cf-ray": "ray-id"}))

    def test_identifies_cloudflare_403(self) -> None:
        with self.assertRaisesRegex(CalendarBlockedError, "Cloudflare protection"):
            _check_response(response(403, {"server": "cloudflare"}))

    def test_generic_403_is_not_mislabeled_as_cloudflare(self) -> None:
        with self.assertRaises(CalendarRequestError) as caught:
            _check_response(response(403, body="private response body must not be shown"))
        self.assertNotIsInstance(caught.exception, CalendarBlockedError)
        self.assertNotIn("private response body", str(caught.exception))

    def test_success_response_passes(self) -> None:
        _check_response(response(200))

    def test_rate_limit_has_actionable_error(self) -> None:
        with self.assertRaisesRegex(CalendarRequestError, "rate limited.*HTTP 429"):
            _check_response(response(429))

    def test_server_errors_are_reported_as_temporary(self) -> None:
        for status in (500, 502, 503):
            with self.subTest(status=status), self.assertRaisesRegex(
                CalendarRequestError, f"temporarily unavailable.*HTTP {status}"
            ):
                _check_response(response(status))


class ClientTests(unittest.TestCase):
    @patch("simulcast_calendar.client.cloudscraper.create_scraper")
    def test_sync_client_uses_locale_date_user_agent_and_proxy(self, create_scraper: Mock) -> None:
        transport = create_scraper.return_value
        transport.headers = {}
        transport.proxies = {}
        transport.get.return_value = response(200, body=HTML)
        client = CalendarClient(
            Locale.PT_BR, user_agent="test-agent", proxy="http://localhost:8080", timeout=7.5,
        )
        week = client.get_week(date(2026, 10, 20))
        self.assertEqual(week.start_date, date(2026, 10, 19))
        self.assertEqual(week.locale, Locale.PT_BR)
        create_scraper.assert_called_once_with()
        self.assertEqual(transport.headers["User-Agent"], "test-agent")
        self.assertEqual(transport.proxies, {"http": "http://localhost:8080", "https": "http://localhost:8080"})
        self.assertIn("/pt-br/simulcastcalendar?", transport.get.call_args.args[0])
        self.assertIn("date=2026-10-20", transport.get.call_args.args[0])
        self.assertEqual(transport.get.call_args.kwargs["timeout"], 7.5)

    @patch("simulcast_calendar.client.cloudscraper.create_scraper")
    def test_sync_client_uses_default_user_agent_without_proxy(self, create_scraper: Mock) -> None:
        transport = create_scraper.return_value
        transport.headers = {}
        transport.proxies = {}
        transport.get.return_value = response(200, body=HTML)
        CalendarClient().get_week(date(2026, 10, 20))
        self.assertEqual(transport.headers["User-Agent"], "simulcast-calendar/0.1.0")
        self.assertEqual(transport.proxies, {})

    @patch("simulcast_calendar.client.cloudscraper.create_scraper")
    def test_get_day_returns_only_the_selected_date(self, create_scraper: Mock) -> None:
        transport = create_scraper.return_value
        transport.headers = {}
        transport.proxies = {}
        transport.get.return_value = response(200, body=HTML)
        day = CalendarClient().get_day(date(2026, 10, 20))
        self.assertEqual(day.date, date(2026, 10, 20))
        self.assertEqual(len(day.releases), 2)
        self.assertIn("date=2026-10-20", transport.get.call_args.args[0])

    def test_client_classifies_cloudflare_challenge(self) -> None:
        with patch("simulcast_calendar.client.cloudscraper.create_scraper") as create_scraper:
            create_scraper.return_value.headers = {}
            create_scraper.return_value.proxies = {}
            create_scraper.return_value.get.return_value = response(403, {"cf-mitigated": "challenge"})
            with self.assertRaises(CalendarBlockedError):
                CalendarClient().get_week(date(2026, 10, 20))

    def test_client_wraps_timeouts(self) -> None:
        with patch("simulcast_calendar.client.cloudscraper.create_scraper") as create_scraper:
            create_scraper.return_value.headers = {}
            create_scraper.return_value.proxies = {}
            create_scraper.return_value.get.side_effect = TimeoutError("late")
            with self.assertRaisesRegex(CalendarRequestError, "timed out after 20s") as caught:
                CalendarClient().get_week(date(2026, 10, 20))
        self.assertIsInstance(caught.exception.__cause__, TimeoutError)

    def test_client_wraps_connection_errors(self) -> None:
        failures = (
            OSError("DNS lookup failed"),
            OSError("proxy unavailable"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch(
                "simulcast_calendar.client.cloudscraper.create_scraper"
            ) as create_scraper:
                create_scraper.return_value.headers = {}
                create_scraper.return_value.proxies = {}
                create_scraper.return_value.get.side_effect = failure
                with self.assertRaisesRegex(CalendarRequestError, "network connection failed") as caught:
                    CalendarClient().get_week(date(2026, 10, 20))
                self.assertIs(caught.exception.__cause__, failure)

    def test_client_exposes_http_errors_as_calendar_errors(self) -> None:
        with patch("simulcast_calendar.client.cloudscraper.create_scraper") as create_scraper:
            create_scraper.return_value.headers = {}
            create_scraper.return_value.proxies = {}
            for status in (429, 503):
                with self.subTest(status=status):
                    create_scraper.return_value.get.return_value = response(status)
                    with self.assertRaises(CalendarRequestError):
                        CalendarClient().get_week(date(2026, 10, 20))


if __name__ == "__main__":
    unittest.main()
