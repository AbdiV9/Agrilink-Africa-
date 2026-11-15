# Owner: Person 2 (Frontend Flet UI Lead)
"""Settings (/settings): language, edit details, text size, dark mode,
help / user manual, about and logout."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

import config
from Auth.auth import logout
from Auth.session import session
from Auth.validation import normalize_phone, validate_email, validate_phone
from UI import components as c
from UI import mock_data as md
from UI import theme
from UI.components import tr
from UI.theme import PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)

LANGUAGES = [("en", "English"), ("sw", "Kiswahili (Swahili)"), ("so", "Soomaali (Somali)"), ("ha", "Hausa"),
             ("yo", "Yorùbá (Yoruba)"), ("am", "አማርኛ (Amharic)"), ("fr", "Français (French)")]
BUILT_IN_LANGUAGES = {"en", "sw", "so"}

HELP_TOPICS = [
    ("help.sell_q", "How do I sell my crops?",
     "help.sell_a", "Tap **Sell**, pick your crop, enter the quantity and your price. The hint shows today's market "
                    "price so you can price fairly. Your listing appears in the Market straight away."),
    ("help.buy_q", "How do I buy?",
     "help.buy_a", "Open a listing from the Market, choose the quantity and tap **Buy now**. You can also tap "
                   "**Message seller** to agree on delivery first. Always check produce before paying."),
    ("help.chart_q", "How do I read the price chart?",
     "help.chart_a", "Green means the price went up over the chosen range, red means down. Switch 1W/1M/3M/1Y to "
                     "zoom. Turn on **Show AI prediction** for a dashed 30-day forecast (an estimate, not a promise)."),
    ("help.alerts_q", "What are price alerts?",
     "help.alerts_a", "On a crop page tap **Set price alert**. We'll notify you when the price goes above or drops "
                      "below your target. Harvest reminders come from the crops you've planted."),
    ("help.verify_q", "How do I get the ✔ verified badge?",
     "help.verify_a", "Open **My profile** and submit a land title, cooperative ID, government registration, subsidy "
                      "enrolment or livestock proof. Our team reviews it within 2 working days."),
    ("help.sms_q", "Can I message people without internet?",
     "help.sms_a", "Yes. Turn on **Send as SMS** in a conversation and the message is also sent to their phone by SMS."),
]


def _section(page: ft.Page, title: str, icon: str, controls: list[ft.Control]) -> ft.Container:
    pal = palette(page)
    return ft.Container(
        padding=14, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([ft.Icon(icon, color=PRIMARY if not theme.is_dark(page) else pal.up),
                    ft.Text(title, size=fs(16), weight=ft.FontWeight.W_700, color=palette().text)]),
            *controls,
        ], spacing=10),
    )


def build_settings_view(page: ft.Page, **params: Any) -> ft.View:
    """All user settings in one scrolling page."""
    pal = palette(page)
    user = session.user or md.MOCK_USER
    uid = int(user["id"])

    def save(fields: dict[str, Any], message: str | None = None, rebuild: bool = False) -> bool:
        """Persist fields, refresh the session and optionally re-apply the theme."""
        try:
            md.call("update_user", uid, fields)
        except ValueError as exc:
            c.show_snack(page, str(exc), error=True)
            return False
        except Exception:
            log.exception("update_user failed")
            c.show_snack(page, tr("settings.save_error", "Couldn't save. Please try again."), error=True)
            return False
        if session.user is not None:
            if md.is_real("update_user"):
                session.refresh()
            else:
                session.user.update(fields)
        if message:
            c.show_snack(page, message)
        if rebuild:
            fresh = session.user or user
            theme.apply_theme(page, bool(fresh.get("dark_mode")), float(fresh.get("text_scale") or 1.0))
            page.go("/settings")
        return True

    # --- language -------------------------------------------------------------
    lang_note = ft.Text("", size=fs(12), color=pal.muted)

    def describe_language(code: str) -> str:
        if code in BUILT_IN_LANGUAGES:
            return tr("settings.lang_builtin", "Menus are translated. The assistant replies in this language.")
        if config.TRANSLATION_ENABLED:
            return tr("settings.lang_deepl", "Menus are translated automatically (DeepL).")
        return tr("settings.lang_partial", "The assistant replies in this language. Menus stay in English "
                                           "until a DeepL key is added.")

    def language_changed(e: ft.ControlEvent) -> None:
        code = e.control.value or "en"
        lang_note.value = describe_language(code)
        save({"language": code}, tr("settings.lang_saved", "Language saved"), rebuild=True)

    lang_dd = ft.Dropdown(value=user.get("language") or "en", expand=True, on_change=language_changed,
                          options=[ft.dropdown.Option(code, label) for code, label in LANGUAGES])
    lang_note.value = describe_language(lang_dd.value)

    # --- appearance -----------------------------------------------------------
    dark_switch = ft.Switch(label=tr("settings.dark", "Dark mode"), value=bool(user.get("dark_mode")),
                            on_change=lambda e: save({"dark_mode": bool(e.control.value)}, rebuild=True))
    current_scale = float(user.get("text_scale") or 1.0)
    scale_label = ft.Text(f"{current_scale:.1f}×", size=fs(13), weight=ft.FontWeight.W_600, color=palette().text)
    sample = ft.Text(tr("settings.sample", "Maize KES 45.20/kg"), size=16 * current_scale, color=palette().text)

    def scale_preview(e: ft.ControlEvent) -> None:
        value = round(float(e.control.value), 1)
        scale_label.value = f"{value:.1f}×"
        sample.size = 16 * value
        scale_label.update()
        sample.update()

    slider = ft.Slider(min=0.8, max=1.6, divisions=8, value=min(1.6, max(0.8, current_scale)),
                       label="{value}×", active_color=PRIMARY, expand=True, on_change=scale_preview,
                       on_change_end=lambda e: save({"text_scale": round(float(e.control.value), 1)}, rebuild=True))

    # --- edit details ---------------------------------------------------------------
    full_name = ft.TextField(label=tr("register.full_name", "Full name"), value=user.get("full_name") or "")
    email = ft.TextField(label=tr("register.email", "Email"), value=user.get("email") or "",
                         keyboard_type=ft.KeyboardType.EMAIL)
    phone = ft.TextField(label=tr("register.phone", "Phone"), value=user.get("phone") or "",
                         keyboard_type=ft.KeyboardType.PHONE)
    region = ft.TextField(label=tr("register.region", "Region or town"), value=user.get("region") or "")
    country = ft.TextField(label=tr("register.country", "Country"), value=user.get("country") or "")
    role = ft.Dropdown(label=tr("settings.role", "I am a"), value=user.get("role") or "farmer", expand=True,
                       options=[ft.dropdown.Option("farmer", "🌾 Farmer"), ft.dropdown.Option("buyer", "🛒 Buyer"),
                                ft.dropdown.Option("both", "🔁 Both")])

    def save_details(e: ft.ControlEvent) -> None:
        for f in (full_name, email, phone, region, country):
            f.error_text = None
        ok_email, msg_email = validate_email(email.value or "")
        ok_phone, msg_phone = validate_phone(phone.value or "")
        if not (full_name.value or "").strip():
            full_name.error_text = tr("register.need_name", "Please enter your full name.")
        if not ok_email:
            email.error_text = msg_email
        if not ok_phone:
            phone.error_text = msg_phone
        if not (region.value or "").strip():
            region.error_text = tr("register.need_region", "Please enter your region or town.")
        if any(f.error_text for f in (full_name, email, phone, region)):
            page.update()
            return
        saved = save({
            "full_name": full_name.value.strip(), "email": email.value.strip(),
            "phone": normalize_phone(phone.value), "region": region.value.strip(),
            "country": (country.value or "").strip(), "role": role.value,
        }, tr("settings.details_saved", "Details saved"))
        if not saved:
            email.error_text = tr("settings.check_email", "Check this email")
        page.update()

    details = ft.ExpansionTile(
        title=ft.Text(tr("settings.edit_details", "Edit my details"), size=fs(15), color=palette().text),
        subtitle=ft.Text(f"@{user['username']} · {user.get('email') or ''}", size=fs(12), color=pal.muted),
        leading=ft.Icon(ft.Icons.PERSON_OUTLINE),
        controls_padding=ft.padding.only(top=8, bottom=8),
        controls=[ft.Column([full_name, email, phone, region, country, ft.Row([role]),
                             ft.FilledButton(tr("settings.save", "Save details"), icon=ft.Icons.SAVE,
                                             on_click=save_details)], spacing=10)],
    )

    # --- help / user manual ---------------------------------------------------------
    help_tiles = [
        ft.ExpansionTile(
            title=ft.Text(tr(qk, q), size=fs(14), color=palette().text),
            controls_padding=ft.padding.only(left=12, right=12, bottom=10),
            controls=[ft.Markdown(tr(ak, a), md_style_sheet=c.markdown_style(13))],
        )
        for qk, q, ak, a in HELP_TOPICS
    ]

    # --- about + logout ---------------------------------------------------------------
    features = config.feature_summary()
    feature_text = " · ".join(f"{'✅' if on else '⚪'} {name.replace('_', ' ')}" for name, on in features.items())

    def confirm_logout(e: ft.ControlEvent) -> None:
        c.confirm_logout(page)

    try:
        unread = md.call("get_unread_count", uid)
    except Exception:
        unread = 0

    return c.app_view(page, "/settings", tr("settings.title", "Settings"), nav="/settings", unread=unread, controls=[
        _section(page, tr("settings.account", "Account"), ft.Icons.MANAGE_ACCOUNTS, [
            ft.ListTile(leading=ft.Icon(ft.Icons.ACCOUNT_CIRCLE), title=ft.Text(tr("profile.mine", "My profile"), color=palette().text),
                        trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT), on_click=lambda e: page.go(f"/profile/{uid}")),
            ft.ListTile(leading=ft.Icon(ft.Icons.RECEIPT_LONG),
                        title=ft.Text(tr("purchases.title", "Purchase history"), color=palette().text),
                        trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT), on_click=lambda e: page.go("/purchases")),
            ft.ListTile(leading=ft.Icon(ft.Icons.NEWSPAPER), title=ft.Text(tr("news.title", "Farming news"), color=palette().text),
                        trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT), on_click=lambda e: page.go("/news")),
            details,
        ]),
        _section(page, tr("settings.language", "Language"), ft.Icons.TRANSLATE, [ft.Row([lang_dd]), lang_note]),
        _section(page, tr("settings.accessibility", "Display & accessibility"), ft.Icons.ACCESSIBILITY_NEW, [
            dark_switch,
            ft.Row([ft.Text(tr("settings.text_size", "Text size"), size=fs(14), color=palette().text), scale_label],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("A", size=12, color=palette().text), slider, ft.Text("A", size=22, color=palette().text)], spacing=4),
            sample,
        ]),
        _section(page, tr("settings.help", "Help & user manual"), ft.Icons.HELP_OUTLINE, help_tiles),
        _section(page, tr("settings.about", "About"), ft.Icons.INFO_OUTLINE, [
            ft.Text(f"{config.APP_NAME} v{config.APP_VERSION}", size=fs(14), weight=ft.FontWeight.W_600, color=palette().text),
            ft.Text(feature_text, size=fs(12), color=pal.muted),
        ]),
        ft.OutlinedButton(tr("settings.logout", "Log out"), icon=ft.Icons.LOGOUT, height=fs(48), on_click=confirm_logout,
                          style=ft.ButtonStyle(color=pal.down, side=ft.BorderSide(1, pal.down))),
        ft.Container(height=8),
    ])
