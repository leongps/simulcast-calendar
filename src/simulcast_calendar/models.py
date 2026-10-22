from dataclasses import dataclass
from datetime import date, datetime

from .locales import (
    Locale,
    audio_language_name,
    audio_locale_for_label,
    episode_group_key,
)


@dataclass(frozen=True, slots=True)
class ReleaseCalendarItem:
    series_id: str
    episode_id: str
    season_title: str
    episode_title: str
    episode_number: float
    release_time: datetime
    premium: bool
    thumbnail_url: str
    audio_locale: str | None = None
    audio_label: str | None = None

    @property
    def audio_language(self) -> str | None:
        return audio_language_name(self.audio_locale or audio_locale_for_label(self.audio_label))


@dataclass(frozen=True, slots=True)
class ReleaseCalendarReleaseGroup:
    episode_id: str
    releases: tuple[ReleaseCalendarItem, ...]

    @property
    def audio_locales(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            locale for release in self.releases
            if (locale := release.audio_locale or audio_locale_for_label(release.audio_label))
        ))

    @property
    def audio_languages(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            language for release in self.releases
            if (language := release.audio_language)
        ))


def _group_releases(releases: tuple[ReleaseCalendarItem, ...]) -> tuple[ReleaseCalendarReleaseGroup, ...]:
    groups: dict[str, list[ReleaseCalendarItem]] = {}
    for release in releases:
        groups.setdefault(episode_group_key(release.episode_id), []).append(release)
    return tuple(
        ReleaseCalendarReleaseGroup(episode_id, tuple(items))
        for episode_id, items in groups.items()
    )


@dataclass(frozen=True, slots=True)
class ReleaseCalendarDay:
    date: date
    releases: tuple[ReleaseCalendarItem, ...]

    def grouped_releases(self) -> tuple[ReleaseCalendarReleaseGroup, ...]:
        return _group_releases(self.releases)


@dataclass(frozen=True, slots=True)
class ReleaseCalendarWeek:
    start_date: date
    days: tuple[ReleaseCalendarDay, ...]
    locale: Locale

    def on(self, day: date) -> tuple[ReleaseCalendarItem, ...]:
        if not self.start_date <= day < date.fromordinal(self.start_date.toordinal() + 7):
            raise ValueError("date is outside this calendar week")
        return self.days[(day - self.start_date).days].releases

    def grouped_releases(self) -> tuple[ReleaseCalendarReleaseGroup, ...]:
        return _group_releases(tuple(release for day in self.days for release in day.releases))
