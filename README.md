# SimulCast-Calendar

A synchronous Python client and command-line tool for Crunchyroll's simulcast calendar. It uses CloudScraper for HTTP requests.

> **Unofficial project:** This library is not affiliated with or endorsed by Crunchyroll. Crunchyroll may change its website or calendar at any time, which can make this library stop working or return outdated information.

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Install

From the project directory:

```bash
python -m pip install -e .
```

After the GitHub repository is created, install directly from Git with:

```bash
python -m pip install "git+https://github.com/leongps/simulcast-calendar.git"
```

For development, clone the repository and install its test dependency with `python -m pip install -e ".[dev]"`.

## Quick start: Python

Fetch today's releases in UTC:

```python
from simulcast_calendar import CalendarClient, Locale

with CalendarClient(locale=Locale.PT_BR) as calendar:
    day = calendar.get_day()
    print(f"{day.date}: {len(day.releases)} releases")

    for release in day.releases:
        print(f"{release.season_title} — Episode {release.episode_number:g}")
```

To fetch only one day's releases from a week, use `week.on(date)`. This filters the week already fetched:

```python
from datetime import date

selected_day = date(2026, 10, 20)
with CalendarClient(locale=Locale.PT_BR) as calendar:
    week = calendar.get_week(selected_day)
    for release in week.on(selected_day):
        print(release.season_title, release.episode_title)
```

Use `get_day(date)` when you want the returned object to contain only that day. To access all seven days, iterate through `week.days`:

```python
from datetime import date

with CalendarClient(locale=Locale.PT_BR) as calendar:
    week = calendar.get_week(date(2026, 10, 20))
    for day in week.days:
        print(day.date, len(day.releases))
```

Crunchyroll returns the whole week for each request. `get_day()` selects the requested date from that week's response. With no date, it uses today's UTC date.

## Quick start: command line

```bash
simulcast-calendar --locale pt-br --day
simulcast-calendar --locale pt-br --day --date 2026-10-20
simulcast-calendar --locale ko-kr --group-dubs
```

You can also run `python -m simulcast_calendar` with the same options. Use `--proxy`, `--user-agent`, and `--timeout` to configure the request. Run `simulcast-calendar --help` to see all options.

Supported locales: `en-us`, `es-419`, `es-es`, `pt-br`, `pt-pt`, `fr-fr`, `de-de`, `ar`, `it-it`, `ru-ru`, `hi-in`, `pl-pl`, `zh-tw`, `th-th`, `tl-ph`, `id-id`, and `ko-kr`.

## Make your own JSON

The library returns dataclasses, so you can choose which fields to include and how to name them. This example exports one day's releases using only Python's standard library:

```python
import json
from datetime import date
from pathlib import Path

from simulcast_calendar import CalendarClient, Locale

with CalendarClient(locale=Locale.PT_BR) as calendar:
    day = calendar.get_day(date(2026, 10, 20))

data = {
    "date": day.date.isoformat(),
    "releases": [
        {
            "title": release.season_title,
            "episode": release.episode_number,
            "episode_title": release.episode_title,
            "release_time": release.release_time.isoformat(),
            "audio_language": release.audio_language,
            "is_premium": release.premium,
            "url": f"https://www.crunchyroll.com/watch/{release.episode_id}",
        }
        for release in day.releases
    ],
}

Path("releases.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

Change the dictionary to add, remove, or rename fields. For a weekly JSON file, iterate through `week.days` and build one entry per day.

`release.premium` is already a Python boolean. `json.dumps()` writes it as the JSON boolean `true` or `false`; do not convert it to the strings `"True"` or `"False"`. The example writes JSON to a file. Use `print()` when you want to display text in the terminal, as the CLI does.

## Multiple audio versions

Releases remain available individually. `week.grouped_releases()` groups entries whose episode IDs share a base ID after removing a recognized audio suffix. `day.grouped_releases()` does the same for a single day:

```python
for group in day.grouped_releases():
    print(group.episode_id, group.audio_languages)
    for release in group.releases:
        print(release.season_title, release.episode_id)
```

Grouping includes only variants present in the fetched data. `audio_locale` and `audio_language` are inferred from an undocumented episode ID convention and should be treated as hints. A recognized language label in the displayed title is available as `audio_label`; the original title is preserved, including labels such as `(English)`.

## Errors and tests

Request timeouts, connection failures, HTTP 429 responses, and server errors raise `CalendarRequestError`. A 403 response with Cloudflare indicators raises `CalendarBlockedError`. Some Cloudflare challenges may still require a full browser.

Install the development dependency and run the test suite with:

```bash
python -m pip install -e ".[dev]"
pytest
```

The GitHub Actions workflow in `.github/workflows/tests.yml` installs the project and runs the test suite on Python 3.11, 3.12, and 3.13 for every push and pull request. It starts running automatically after the repository is created on GitHub; no PyPI account or publishing setup is needed.
