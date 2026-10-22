import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urljoin, urlparse

import cloudscraper
from bs4 import BeautifulSoup, Tag

from .locales import Locale, audio_label_from_title, audio_locale_for_episode_id
from .models import ReleaseCalendarDay, ReleaseCalendarItem, ReleaseCalendarWeek

_BASE_URL = "https://www.crunchyroll.com"
_CALENDAR_PATH = "/simulcastcalendar"
_SERIES_ID = re.compile(r"/series/([^/?#]+)")
_EPISODE_ID = re.compile(r"/watch/(?:musicvideo/|concert/)?([^/?#]+)")


class CalendarError(Exception):
    pass


class CalendarRequestError(CalendarError):
    pass


class CalendarBlockedError(CalendarRequestError):
    pass


def _check_response(response) -> None:
    if response.status_code < 400:
        return
    message = f"Crunchyroll returned HTTP {response.status_code} for {response.url}"
    body = response.text[:100_000].lower()
    server = response.headers.get("server", "").lower()
    challenge = response.headers.get("cf-mitigated", "").lower() == "challenge"
    cloudflare = (
        challenge
        or "cf-ray" in response.headers
        or "cloudflare" in server
        or "cf-chl-" in body
        or "attention required! | cloudflare" in body
    )
    if response.status_code == 403 and cloudflare:
        if challenge:
            raise CalendarBlockedError(
                f"{message}; Cloudflare returned a browser challenge "
                "(cf-mitigated: challenge). A User-Agent header alone cannot complete this challenge."
            )
        raise CalendarBlockedError(
            f"{message}; the response indicates Cloudflare protection and the request was blocked."
        )
    if response.status_code == 429:
        raise CalendarRequestError(f"Crunchyroll rate limited the request (HTTP 429) for {response.url}")
    if response.status_code >= 500:
        raise CalendarRequestError(f"Crunchyroll is temporarily unavailable (HTTP {response.status_code}) for {response.url}")
    raise CalendarRequestError(message)


def _calendar_url(locale: Locale, day: date) -> str:
    return f"{_BASE_URL}{locale.path}{_CALENDAR_PATH}?filter=premium&date={day:%Y-%m-%d}"


def _required(root: Tag, selector: str, attr: str | None = None) -> str:
    element = root.select_one(selector)
    value = element.get(attr) if element and attr else element.get_text(strip=True) if element else None
    if not value:
        raise CalendarError(f"calendar markup is missing {selector}")
    return str(value)


def _parse_week(html: str, week_start: date, locale: Locale) -> ReleaseCalendarWeek:
    soup = BeautifulSoup(html, "html.parser")
    days_element = soup.select_one("ol.days")
    if days_element is None:
        raise CalendarError("calendar markup is missing ol.days")

    days = []
    day_elements = days_element.select(":scope > li.day")
    if len(day_elements) != 7:
        raise CalendarError(f"expected 7 calendar days, got {len(day_elements)}")

    for index, day_element in enumerate(day_elements):
        releases = []
        release_list = day_element.select_one("ol.releases")
        for release in release_list.find_all(recursive=False) if release_list else ():
            season = release.select_one("h1.season-name")
            episode = release.select_one("article.featured-episode")
            if season is None or episode is None:
                raise CalendarError("calendar markup is missing a release entry")

            series_url = _required(season, '[itemprop="url"]', "href")
            episode_url = _required(episode, '[itemprop="url"]', "href")
            series_match = _SERIES_ID.search(urlparse(urljoin(_BASE_URL, series_url)).path)
            episode_path = urlparse(urljoin(_BASE_URL, episode_url)).path.rstrip("/")
            episode_match = _EPISODE_ID.search(episode_path)
            if not series_match or not episode_match:
                raise CalendarError("calendar markup contains an unrecognized Crunchyroll URL")

            try:
                release_time = datetime.fromisoformat(
                    _required(episode, '[itemprop="datePublished"]', "content").replace("Z", "+00:00")
                )
                if release_time.tzinfo is None:
                    raise ValueError("release time has no timezone")
                release_time = release_time.astimezone(UTC)
                episode_number = float(_required(episode, '[itemprop="episodeNumber"]', "content"))
            except ValueError as error:
                raise CalendarError("calendar markup contains an invalid episode date or number") from error

            releases.append(ReleaseCalendarItem(
                series_id=series_match.group(1),
                episode_id=episode_match.group(1),
                season_title=_required(season, '[itemprop="name"]'),
                episode_title=_required(episode, '[itemprop="name"]'),
                episode_number=episode_number,
                release_time=release_time,
                premium=episode.select_one("svg.premium-flag") is not None,
                thumbnail_url=_required(episode, '[itemprop="image"]', "src"),
                audio_locale=audio_locale_for_episode_id(episode_match.group(1)),
                audio_label=audio_label_from_title(_required(season, '[itemprop="name"]')),
            ))
        days.append(ReleaseCalendarDay(week_start + timedelta(days=index), tuple(releases)))

    return ReleaseCalendarWeek(week_start, tuple(days), locale)


class CalendarClient:
    def __init__(
        self,
        locale: Locale = Locale.EN_US,
        *,
        user_agent: str = "simulcast-calendar/0.1.0",
        proxy: str | None = None,
        timeout: float = 20,
    ) -> None:
        self.locale = Locale(locale)
        self._client = cloudscraper.create_scraper()
        self._client.headers["User-Agent"] = user_agent
        if proxy:
            self._client.proxies.update({"http": proxy, "https": proxy})
        self._timeout = timeout

    def get_week(self, day: date | None = None) -> ReleaseCalendarWeek:
        day = day or datetime.now(UTC).date()
        if isinstance(day, datetime):
            day = day.date()
        url = _calendar_url(self.locale, day)
        try:
            response = self._client.get(url, timeout=self._timeout)
        except OSError as error:
            if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.casefold():
                message = f"request timed out after {self._timeout:g}s for {url}"
            else:
                message = f"network connection failed for {url}; check DNS, network, and proxy settings"
            raise CalendarRequestError(message) from error
        _check_response(response)
        return _parse_week(response.text, day - timedelta(days=day.weekday()), self.locale)

    def get_day(self, day: date | None = None) -> ReleaseCalendarDay:
        day = day or datetime.now(UTC).date()
        if isinstance(day, datetime):
            day = day.date()
        week = self.get_week(day)
        return week.days[(day - week.start_date).days]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CalendarClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
