from enum import Enum

_AUDIO_LOCALES = {
    "ARSA": ("ar-SA", "Arabic"),
    "CAES": ("ca-ES", "Catalan"),
    "DEDE": ("de-DE", "German"),
    "ENIN": ("en-IN", "English (India)"),
    "ENUS": ("en-US", "English (US)"),
    "ES419": ("es-419", "Spanish (Latin America)"),
    "ESES": ("es-ES", "Spanish (Spain)"),
    "FRFR": ("fr-FR", "French"),
    "HIIN": ("hi-IN", "Hindi"),
    "IDID": ("id-ID", "Indonesian"),
    "ITIT": ("it-IT", "Italian"),
    "JAJP": ("ja-JP", "Japanese"),
    "KOKR": ("ko-KR", "Korean"),
    "MSMY": ("ms-MY", "Malay"),
    "PLPL": ("pl-PL", "Polish"),
    "PTBR": ("pt-BR", "Portuguese (Brazil)"),
    "PTPT": ("pt-PT", "Portuguese (Portugal)"),
    "RURU": ("ru-RU", "Russian"),
    "TAIN": ("ta-IN", "Tamil"),
    "TEIN": ("te-IN", "Telugu"),
    "THTH": ("th-TH", "Thai"),
    "TLPH": ("tl-PH", "Filipino"),
    "TRTR": ("tr-TR", "Turkish"),
    "VIVN": ("vi-VN", "Vietnamese"),
    "ZHCN": ("zh-CN", "Chinese (China)"),
    "ZHHK": ("zh-HK", "Chinese (Hong Kong)"),
    "ZHTW": ("zh-TW", "Chinese (Taiwan)"),
}

_AUDIO_LABELS = {
    "arabic": "ar-SA",
    "العربية": "ar-SA",
    "catalan": "ca-ES",
    "chinese (china)": "zh-CN",
    "chinese (taiwan)": "zh-TW",
    "deutsch": "de-DE",
    "english": "en-US",
    "english (india)": "en-IN",
    "english (us)": "en-US",
    "español (américa latina)": "es-419",
    "español (españa)": "es-ES",
    "filipino": "tl-PH",
    "français (france)": "fr-FR",
    "french": "fr-FR",
    "german": "de-DE",
    "hindi": "hi-IN",
    "हिन्दी": "hi-IN",
    "हिंदी": "hi-IN",
    "indonesian": "id-ID",
    "italian": "it-IT",
    "italiano": "it-IT",
    "japanese": "ja-JP",
    "한국어": "ko-KR",
    "korean": "ko-KR",
    "polish": "pl-PL",
    "polski": "pl-PL",
    "português (brasil)": "pt-BR",
    "português (portugal)": "pt-PT",
    "russian": "ru-RU",
    "русский": "ru-RU",
    "spanish (latin america)": "es-419",
    "spanish (spain)": "es-ES",
    "tagalog": "tl-PH",
    "tamil": "ta-IN",
    "தமிழ்": "ta-IN",
    "telugu": "te-IN",
    "తెలుగు": "te-IN",
    "thai": "th-TH",
    "ไทย": "th-TH",
    "中文 (台灣)": "zh-TW",
    "bahasa indonesia": "id-ID",
}


def _audio_suffix(episode_id: str) -> tuple[str, str] | None:
    episode_id = episode_id.upper()
    for suffix in sorted(_AUDIO_LOCALES, key=len, reverse=True):
        if episode_id.endswith(suffix):
            return suffix, _AUDIO_LOCALES[suffix][0]
    return None


def audio_locale_for_episode_id(episode_id: str) -> str | None:
    suffix = _audio_suffix(episode_id)
    return suffix[1] if suffix else None


def audio_locale_for_label(label: str | None) -> str | None:
    return _AUDIO_LABELS.get(label.casefold().strip()) if label else None


def audio_label_from_title(title: str) -> str | None:
    if not title.endswith(")"):
        return None
    depth = 0
    for index in range(len(title) - 1, -1, -1):
        if title[index] == ")":
            depth += 1
        elif title[index] == "(":
            depth -= 1
            if depth == 0:
                label = title[index + 1:-1].strip()
                return label if audio_locale_for_label(label) else None
    return None


def episode_group_key(episode_id: str) -> str:
    suffix = _audio_suffix(episode_id)
    return episode_id[:-len(suffix[0])] if suffix else episode_id


def audio_language_name(locale: str | None) -> str | None:
    return next((name for code, name in _AUDIO_LOCALES.values() if code == locale), None)


class Locale(str, Enum):
    EN_US = "en-US"
    ES_419 = "es-419"
    ES_ES = "es-ES"
    PT_BR = "pt-BR"
    PT_PT = "pt-PT"
    FR_FR = "fr-FR"
    DE_DE = "de-DE"
    AR = "ar"
    IT_IT = "it-IT"
    RU_RU = "ru-RU"
    HI_IN = "hi-IN"
    PL_PL = "pl-PL"
    ZH_TW = "zh-TW"
    TH_TH = "th-TH"
    TL_PH = "tl-PH"
    ID_ID = "id-ID"
    KO_KR = "ko-KR"

    @property
    def path(self) -> str:
        return {
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
        }[self]
