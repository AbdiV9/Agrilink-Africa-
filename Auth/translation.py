# Owner: Person 3 (Integration, Logic & API Lead)
"""Translation: built-in Swahili and Somali UI strings, plus DeepL for anything else.

* ``t(key, default=None, lang=None)`` returns the UI string for ``key`` in
  the logged-in user's language. Swahili (sw) and Somali (so) come from the
  built-in dictionary below. Other languages are machine-translated from
  ``default`` when a DeepL key is set. Otherwise (and for English) it
  returns ``key`` unchanged, which tells ``UI.components.tr`` to use its
  English default.
* ``translate(text, target_lang)`` translates free text via DeepL, cached in
  memory, and returns the original text on any failure.

Placeholders such as ``{crop}`` must stay untranslated in every string.
"""

from __future__ import annotations

import logging
from typing import Any

import config

log = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"en": "English", "sw": "Kiswahili", "so": "Soomaali", "ha": "Hausa", "yo": "Yorùbá",
                       "am": "አማርኛ", "fr": "Français"}
# DeepL target codes (DeepL doesn't support every African language; failures fall back to English).
DEEPL_CODES = {"en": "EN-GB", "fr": "FR", "sw": "SW", "so": "SO", "ha": "HA", "yo": "YO", "am": "AM"}

STRINGS: dict[str, dict[str, str]] = {
    "sw": {
        # navigation
        "news.title": "Habari za kilimo", "news.home_title": "Habari za kilimo", "news.see_all": "Ona zote",
        "news.all": "Zote", "news.loading": "Inapakia habari…", "purchases.title": "Historia ya ununuzi",
        "purchases.bought": "Nilivyonunua", "purchases.sold": "Nilivyouza", "purchases.spent": "Matumizi",
        "purchases.earned": "Mapato", "purchases.orders": "Oda",
        "login.show_password": "Onyesha nenosiri",
        "nav.home": "Nyumbani", "nav.market": "Soko", "nav.sell": "Uza", "nav.messages": "Ujumbe",
        "nav.settings": "Mipangilio",
        # common
        "common.cancel": "Ghairi", "common.refresh": "Onyesha upya",
        # login / register
        "login.title": "Karibu tena", "login.subtitle": "Ingia ili kununua, kuuza na kufuatilia bei za mazao.",
        "login.username": "Jina la mtumiaji", "login.password": "Nenosiri", "login.button": "Ingia",
        "login.no_account": "Mgeni kwenye AgriLink?", "login.register_link": "Fungua akaunti",
        "login.tagline": "Bei za haki, kutoka shambani hadi sokoni.",
        "login.need_username": "Weka jina la mtumiaji", "login.need_password": "Weka nenosiri",
        "register.title": "Jiunge na AgriLink Africa", "register.button": "Fungua akaunti",
        "register.i_am": "Mimi ni…", "register.full_name": "Jina kamili", "register.email": "Barua pepe",
        "register.phone": "Simu", "register.password": "Nenosiri", "register.confirm": "Thibitisha nenosiri",
        "register.country": "Nchi", "register.region": "Mkoa au mji", "register.login_link": "Ingia",
        # home
        "home.morning": "Habari za asubuhi", "home.afternoon": "Habari za mchana", "home.evening": "Habari za jioni",
        "home.ask_ai": "Uliza AgriLink AI", "home.sell": "Uza mazao", "home.alerts_title": "Arifa",
        "home.watch_title": "Mazao unayofuatilia", "home.weather_title": "Hali ya hewa",
        "home.see_markets": "Masoko", "home.browse": "Tazama soko",
        "home.harvest_soon": "Vuna {crop} baada ya siku {n}", "home.harvest_today": "Vuna {crop} yako leo",
        "home.alert_hit": "Lengo limefikiwa! Sasa {price}", "home.alert_now": "Sasa {price}",
        "home.no_alerts": "Hakuna arifa kwa sasa", "home.watch_empty": "Hujafuatilia zao lolote",
        "home.weather_loading": "Inapakia hali ya hewa…", "home.profile": "Wasifu wangu",
        # market / crop / listing
        "market.title": "Soko", "market.tab_listings": "Bidhaa", "market.tab_markets": "Masoko",
        "market.count": "Bidhaa {n}", "market.none": "Hakuna bidhaa zinazolingana",
        "market.summary": "Mazao {up} kati ya {n} yamepanda bei wiki hii",
        "market.watch_added": "{crop} imeongezwa kwenye orodha yako",
        "crop.set_alert": "Weka arifa ya bei", "crop.watch": "Fuatilia", "crop.watching": "Unafuatilia",
        "crop.show_prediction": "Onyesha utabiri wa AI", "crop.season_advice": "Ushauri wa msimu",
        "crop.plant": "Panda", "crop.harvest": "Vuna", "crop.growth": "Ukuaji", "crop.sellers": "Wauzaji ({n})",
        "crop.above": "Ikipanda juu ya", "crop.below": "Ikishuka chini ya", "crop.save_alert": "Hifadhi arifa",
        "crop.back_market": "Rudi sokoni",
        "listing.buy_now": "Nunua sasa", "listing.buy": "Nunua", "listing.message": "Mtumie muuzaji ujumbe",
        "listing.seller": "Muuzaji", "listing.available": "{q} {unit} zinapatikana",
        "listing.how_much": "Unahitaji kiasi gani?", "listing.total": "Jumla: {amount}",
        "listing.sold": "Imeuzwa yote", "listing.confirm_title": "Thibitisha ununuzi",
        # sell
        "sell.title": "Uza mavuno yako", "sell.crop": "Unauza nini?", "sell.quantity": "Kiasi",
        "sell.price": "Bei kwa kipimo", "sell.location": "Mahali pa kuchukua", "sell.description": "Maelezo",
        "sell.publish": "Chapisha", "sell.use_market": "Tumia bei ya soko",
        "sell.market_hint": "Bei ya soko leo: {price}/{unit} ({chg} wiki hii)",
        "sell.published": "Bidhaa yako iko hewani! 🎉",
        # messages / chat
        "messages.title": "Ujumbe", "messages.type": "Andika ujumbe…", "messages.send": "Tuma",
        "messages.as_sms": "Tuma kama SMS", "messages.empty": "Bado hakuna ujumbe",
        "chat.title": "AgriLink AI", "chat.ask": "Uliza kuhusu mazao, bei au hali ya hewa…",
        "chat.thinking": "AgriLink AI inafikiri…", "chat.clear": "Futa mazungumzo",
        "chat.p_plant": "Nipande nini mwezi huu?", "chat.p_sell_maize": "Wakati gani bora kuuza mahindi yangu?",
        "chat.p_trend": "Eleza mwenendo huu wa bei", "chat.p_tomatoes": "Tafuta nyanya za bei nafuu karibu nami",
        "chat.p_summary": "Fupisha soko la leo",
        # profile / settings
        "profile.title": "Wasifu", "profile.mine": "Wasifu wangu", "profile.message": "Ujumbe",
        "profile.review": "Toa maoni", "profile.get_verified": "Thibitishwa", "profile.planted": "Mazao yaliyopandwa",
        "profile.listings": "Bidhaa", "profile.reviews": "Maoni", "profile.rating": "Ukadiriaji",
        "settings.title": "Mipangilio", "settings.language": "Lugha", "settings.dark": "Hali ya giza",
        "settings.text_size": "Ukubwa wa maandishi", "settings.help": "Msaada na mwongozo",
        "settings.logout": "Toka", "settings.account": "Akaunti", "settings.edit_details": "Badilisha taarifa zangu",
        "settings.save": "Hifadhi", "settings.about": "Kuhusu", "settings.lang_saved": "Lugha imehifadhiwa",
        "settings.accessibility": "Mwonekano na ufikivu",
    },
    "so": {
        "news.title": "Wararka beeraha", "news.home_title": "Wararka beeraha", "news.see_all": "Dhammaan",
        "news.all": "Dhammaan", "news.loading": "Wararka waa la soo rarayaa…", "purchases.title": "Taariikhda iibsiga",
        "purchases.bought": "Waan iibsaday", "purchases.sold": "Waan iibiyay", "purchases.spent": "Kharash",
        "purchases.earned": "Dakhli", "purchases.orders": "Dalabaad",
        "login.show_password": "Muuji erayga sirta",
        "nav.home": "Hoyga", "nav.market": "Suuqa", "nav.sell": "Iibi", "nav.messages": "Fariimaha",
        "nav.settings": "Dejinta",
        "common.cancel": "Jooji", "common.refresh": "Cusboonaysii",
        "login.title": "Ku soo dhawoow mar kale", "login.subtitle": "Gal si aad u iibsato, u iibiso oo ula socoto qiimaha dalagga.",
        "login.username": "Magaca isticmaalaha", "login.password": "Furaha sirta", "login.button": "Gal",
        "login.no_account": "Ku cusub AgriLink?", "login.register_link": "Samee akoon",
        "login.tagline": "Qiimo cadaalad ah, beerta ilaa suuqa.",
        "login.need_username": "Geli magaca isticmaalaha", "login.need_password": "Geli furaha sirta",
        "register.title": "Ku biir AgriLink Africa", "register.button": "Samee akoon", "register.i_am": "Waxaan ahay…",
        "register.full_name": "Magaca oo buuxa", "register.email": "Iimayl", "register.phone": "Taleefan",
        "register.password": "Furaha sirta", "register.confirm": "Xaqiiji furaha sirta", "register.country": "Dalka",
        "register.region": "Gobolka ama magaalada", "register.login_link": "Gal",
        "home.morning": "Subax wanaagsan", "home.afternoon": "Galab wanaagsan", "home.evening": "Fiid wanaagsan",
        "home.ask_ai": "Weydii AgriLink AI", "home.sell": "Iibi dalag", "home.alerts_title": "Digniinaha",
        "home.watch_title": "Dalagga aad la socoto", "home.weather_title": "Cimilada", "home.see_markets": "Suuqyada",
        "home.browse": "Eeg suuqa", "home.harvest_soon": "Goo {crop} {n} maalmood kadib",
        "home.harvest_today": "Maanta goo {crop}", "home.alert_hit": "Hadafka waa la gaaray! Hadda {price}",
        "home.alert_now": "Hadda {price}", "home.no_alerts": "Hadda digniin ma jirto",
        "home.watch_empty": "Weli dalag lama socotid", "home.weather_loading": "Cimilada waa la soo rarayaa…",
        "home.profile": "Bogga aan leeyahay",
        "market.title": "Suuqa", "market.tab_listings": "Alaabta", "market.tab_markets": "Suuqyada",
        "market.count": "{n} alaab", "market.none": "Wax u dhigma lama helin",
        "market.summary": "{up} ka mid ah {n} dalag ayaa qiimahoodu kordhay toddobaadkan",
        "market.watch_added": "{crop} waxaa lagu daray liiskaaga",
        "crop.set_alert": "Deji digniin qiime", "crop.watch": "La soco", "crop.watching": "Waad la socotaa",
        "crop.show_prediction": "Tus saadaasha AI", "crop.season_advice": "Talo xilliyeed",
        "crop.plant": "Beer", "crop.harvest": "Goo", "crop.growth": "Koritaan", "crop.sellers": "Iibiyeyaasha ({n})",
        "crop.above": "Haddii uu ka sarreeyo", "crop.below": "Haddii uu ka hooseeyo",
        "crop.save_alert": "Kaydi digniinta", "crop.back_market": "Ku noqo suuqa",
        "listing.buy_now": "Iibso hadda", "listing.buy": "Iibso", "listing.message": "Fariin u dir iibiyaha",
        "listing.seller": "Iibiyaha", "listing.available": "{q} {unit} ayaa diyaar ah",
        "listing.how_much": "Immisa ayaad u baahan tahay?", "listing.total": "Wadarta: {amount}",
        "listing.sold": "Waa la iibiyay", "listing.confirm_title": "Xaqiiji iibka",
        "sell.title": "Iibi wax soo saarkaaga", "sell.crop": "Maxaad iibinaysaa?", "sell.quantity": "Tirada",
        "sell.price": "Qiimaha halkii", "sell.location": "Goobta laga qaadanayo", "sell.description": "Faahfaahin",
        "sell.publish": "Daabac", "sell.use_market": "Isticmaal qiimaha suuqa",
        "sell.market_hint": "Qiimaha suuqa maanta: {price}/{unit} ({chg} toddobaadkan)",
        "sell.published": "Alaabtaadu waa la daabacay! 🎉",
        "messages.title": "Fariimaha", "messages.type": "Qor fariin…", "messages.send": "Dir",
        "messages.as_sms": "U dir SMS ahaan", "messages.empty": "Weli fariin ma jirto",
        "chat.title": "AgriLink AI", "chat.ask": "Wax ka weydii dalagga, qiimaha ama cimilada…",
        "chat.thinking": "AgriLink AI way fakaraysaa…", "chat.clear": "Tirtir sheekada",
        "chat.p_plant": "Maxaan beeraa bishan?", "chat.p_sell_maize": "Goorma ayaa ugu fiican in aan iibiyo galleydayda?",
        "chat.p_trend": "Ii sharax isbeddelkan qiimaha", "chat.p_tomatoes": "Ii hel yaanyada ugu jaban ee ii dhow",
        "chat.p_summary": "Soo koob suuqa maanta",
        "profile.title": "Bogga", "profile.mine": "Bogga aan leeyahay", "profile.message": "Fariin",
        "profile.review": "Qor faallo", "profile.get_verified": "Hel xaqiijin", "profile.planted": "Dalagga la beeray",
        "profile.listings": "Alaabta", "profile.reviews": "Faallooyin", "profile.rating": "Qiimeyn",
        "settings.title": "Dejinta", "settings.language": "Luqadda", "settings.dark": "Habka mugdiga",
        "settings.text_size": "Cabbirka qoraalka", "settings.help": "Caawimaad iyo hage",
        "settings.logout": "Ka bax", "settings.account": "Akoonka", "settings.edit_details": "Wax ka beddel xogtayda",
        "settings.save": "Kaydi", "settings.about": "Ku saabsan", "settings.lang_saved": "Luqadda waa la kaydiyay",
        "settings.accessibility": "Muuqaalka iyo gelitaanka",
    },
}

_translator: Any = None
_translate_cache: dict[tuple[str, str], str] = {}
_deepl_failed_langs: set[str] = set()


def current_language() -> str:
    """The logged-in user's language code (defaults to 'en')."""
    try:
        from Auth.session import session

        return ((session.user or {}).get("language") or "en").lower()
    except Exception:
        return "en"


def _get_translator() -> Any:
    global _translator
    if _translator is None and config.TRANSLATION_ENABLED:
        try:
            import deepl

            _translator = deepl.Translator(config.DEEPL_KEY)
        except Exception:
            log.exception("DeepL could not be initialised")
            _translator = False
    return _translator or None


def translate(text: str, target_lang: str) -> str:
    """Translate free text with DeepL; returns ``text`` unchanged if not possible."""
    lang = (target_lang or "en").lower()
    if not text or lang == "en" or lang in _deepl_failed_langs:
        return text
    key = (text, lang)
    if key in _translate_cache:
        return _translate_cache[key]
    translator = _get_translator()
    if translator is None:
        return text
    try:
        result = translator.translate_text(text, target_lang=DEEPL_CODES.get(lang, lang.upper()),
                                           preserve_formatting=True)
        translated = str(getattr(result, "text", result))
    except Exception as exc:
        log.warning("DeepL can't translate to %s (%s); showing English.", lang, exc)
        _deepl_failed_langs.add(lang)
        return text
    _translate_cache[key] = translated
    return translated


def t(key: str, default: str | None = None, lang: str | None = None) -> str:
    """UI string for ``key`` in the user's language (``key`` itself if none)."""
    code = (lang or current_language()).lower()
    if code == "en":
        return key
    built_in = STRINGS.get(code, {}).get(key)
    if built_in:
        return built_in
    if default and config.TRANSLATION_ENABLED:
        translated = translate(default, code)
        if translated != default:
            return translated
    return key
