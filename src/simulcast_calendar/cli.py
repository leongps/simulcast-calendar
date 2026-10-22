import argparse
import sys
from datetime import date
from typing import Sequence

from . import CalendarClient, CalendarError, Locale
from .models import ReleaseCalendarDay, ReleaseCalendarItem, ReleaseCalendarWeek


def _locale_choices() -> dict[str, Locale]:
    return {locale.value.lower(): locale for locale in Locale}


def _parser() -> argparse.ArgumentParser:
    locales = _locale_choices()
    parser = argparse.ArgumentParser(description="Fetch the Crunchyroll simulcast calendar.")
    parser.add_argument("--locale", choices=locales, default=Locale.EN_US.value.lower())
    parser.add_argument("--date", type=date.fromisoformat, help="Date in YYYY-MM-DD format; defaults to today in UTC.")
    parser.add_argument("--day", action="store_true", help="Show one date instead of the full week (today by default).")
    parser.add_argument("--proxy", help="Proxy URL, such as http://localhost:8080.")
    parser.add_argument("--user-agent", default="simulcast-calendar/0.1.0")
    parser.add_argument("--timeout", type=float, default=20, help="Request timeout in seconds.")
    parser.add_argument("--group-dubs", action="store_true", help="Group calendar entries by episode ID.")
    return parser


def _print_header(week: ReleaseCalendarWeek, group_dubs: bool) -> None:
    print("SimulCast-Calendar")
    print(f"Locale: {week.locale.value}")
    print(f"Week: {week.start_date.isoformat()} – {week.days[-1].date.isoformat()}")
    if group_dubs:
        print("View: grouped by episode")


def _print_release(release: ReleaseCalendarItem, *, date_prefix: bool = False) -> None:
    prefix = f"{release.release_time:%Y-%m-%d}  " if date_prefix else ""
    status = "Premium" if release.premium else "Free"
    print(f"  {prefix}{release.release_time:%H:%M} UTC  ·  {status}")
    print(f"    {release.season_title}")
    print(f"    Episode {release.episode_number:g}: {release.episode_title}")
    language = release.audio_language or release.audio_label
    if language:
        print(f"    Audio: {language}")
    print(f"    https://www.crunchyroll.com/watch/{release.episode_id}")


def _print_week(week: ReleaseCalendarWeek, group_dubs: bool) -> None:
    _print_header(week, group_dubs)
    if group_dubs:
        for group in week.grouped_releases():
            print(f"\n{group.episode_id}  ·  {len(group.releases)} versions")
            for release in group.releases:
                _print_release(release, date_prefix=True)
        return

    for day in week.days:
        count = len(day.releases)
        unit = "release" if count == 1 else "releases"
        print(f"\n{day.date.isoformat()}  ·  {count} {unit}")
        for index, release in enumerate(day.releases):
            if index:
                print()
            _print_release(release)


def _print_day(day: ReleaseCalendarDay, locale: Locale, group_dubs: bool) -> None:
    count = len(day.releases)
    unit = "release" if count == 1 else "releases"
    print("SimulCast-Calendar")
    print(f"Locale: {locale.value}")
    print(f"Date: {day.date.isoformat()}  ·  {count} {unit}")
    if not day.releases:
        print("No releases scheduled.")
        return
    if group_dubs:
        for group in day.grouped_releases():
            print(f"\n{group.episode_id}  ·  {len(group.releases)} versions")
            for release in group.releases:
                _print_release(release)
        return
    for index, release in enumerate(day.releases):
        if index:
            print()
        _print_release(release)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        with CalendarClient(
            _locale_choices()[args.locale],
            user_agent=args.user_agent,
            proxy=args.proxy,
            timeout=args.timeout,
        ) as client:
            if args.day:
                _print_day(client.get_day(args.date), client.locale, args.group_dubs)
            else:
                _print_week(client.get_week(args.date), args.group_dubs)
    except CalendarError as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0
