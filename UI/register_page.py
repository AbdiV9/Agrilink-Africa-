# Owner: Person 2 (Frontend Flet UI Lead)
"""Registration screen (/register) with inline validation from Auth.validation."""

from __future__ import annotations

import flet as ft

from Auth.auth import register_user
from Auth.session import session
from Auth.validation import (AFRICAN_CALLING_CODES, validate_email, validate_password, validate_phone,
                             validate_registration, validate_username)
from UI import theme
from UI.components import show_snack, tr
from UI.theme import PAD, PRIMARY, RADIUS, fs, palette

# Country name -> calling code, main markets first, then the rest alphabetically.
_MAIN = ["Kenya", "Nigeria", "Ghana", "Uganda", "Somalia"]
COUNTRY_CODES: dict[str, str] = {country: code for code, (country, _) in AFRICAN_CALLING_CODES.items()}
COUNTRIES = _MAIN + sorted(c for c in COUNTRY_CODES if c not in _MAIN)

ROLE_OPTIONS = [("farmer", "🌾 Farmer"), ("buyer", "🛒 Buyer"), ("both", "🔁 Both")]


def build_register_view(page: ft.Page, **params: object) -> ft.View:
    """Full sign-up form: username, full name, email, phone, password + confirm, role, country, region."""
    pal = palette(page)

    def field(label: str, icon: str, **kwargs: object) -> ft.TextField:
        return ft.TextField(label=label, prefix_icon=icon, text_size=fs(15), border_radius=12, **kwargs)

    username = field(tr("register.username", "Username"), ft.Icons.ALTERNATE_EMAIL,
                     helper_text=tr("register.username_help", "3-20 letters, numbers or _"), autocorrect=False)
    full_name = field(tr("register.full_name", "Full name"), ft.Icons.BADGE_OUTLINED,
                      capitalization=ft.TextCapitalization.WORDS)
    email = field(tr("register.email", "Email"), ft.Icons.EMAIL_OUTLINED, keyboard_type=ft.KeyboardType.EMAIL)
    phone = field(tr("register.phone", "Phone"), ft.Icons.PHONE_OUTLINED, keyboard_type=ft.KeyboardType.PHONE,
                  hint_text="+254712345678")
    password = field(tr("register.password", "Password"), ft.Icons.LOCK_OUTLINE, password=True,
                     can_reveal_password=True,
                     helper_text=tr("register.password_help", "8+ chars with A-Z, a-z, 0-9 and a symbol"))
    confirm = field(tr("register.confirm", "Confirm password"), ft.Icons.LOCK_RESET, password=True,
                    can_reveal_password=True)
    region = field(tr("register.region", "Region or town"), ft.Icons.LOCATION_ON_OUTLINED,
                   hint_text="e.g. Nakuru", capitalization=ft.TextCapitalization.WORDS)
    country = ft.Dropdown(
        label=tr("register.country", "Country"), leading_icon=ft.Icons.PUBLIC, value="Kenya", expand=True,
        options=[ft.dropdown.Option(c) for c in COUNTRIES], text_size=fs(15), border_radius=12,
    )
    role = ft.SegmentedButton(
        segments=[ft.Segment(value=v, label=ft.Text(label, size=fs(13), color=palette().text)) for v, label in ROLE_OPTIONS],
        selected={"farmer"}, show_selected_icon=False, allow_empty_selection=False,
    )
    def toggle_show(e: ft.ControlEvent) -> None:
        for f in (password, confirm):  # dots when unticked, plain text when ticked
            f.password = not show_password.value
        page.update()

    show_password = ft.Checkbox(label=tr("login.show_password", "Show password"), value=False,
                                on_change=toggle_show, active_color=PRIMARY,
                                label_style=ft.TextStyle(size=fs(14), color=pal.text))
    role_error = ft.Text("", color=pal.down, size=fs(12), visible=False)
    form_error = ft.Text("", color=pal.down, size=fs(13), visible=False)

    fields: dict[str, ft.Control] = {
        "username": username, "full_name": full_name, "email": email, "phone": phone,
        "password": password, "confirm_password": confirm, "country": country, "region": region,
    }

    # --- live validation when leaving a field ---------------------------
    def check_on_blur(control: ft.TextField, validator) -> None:
        def handler(e: ft.ControlEvent) -> None:
            if control.value:
                ok, msg = validator(control.value)
                control.error_text = None if ok else msg
                control.update()
        control.on_blur = handler

    check_on_blur(username, validate_username)
    check_on_blur(email, validate_email)
    check_on_blur(phone, validate_phone)
    check_on_blur(password, validate_password)

    def confirm_blur(e: ft.ControlEvent) -> None:
        if confirm.value:
            confirm.error_text = None if confirm.value == password.value else tr(
                "register.mismatch", "Passwords don't match.")
            confirm.update()
    confirm.on_blur = confirm_blur

    def country_changed(e: ft.ControlEvent) -> None:
        """Pre-fill the calling code when the phone box is empty or only has a code."""
        code = COUNTRY_CODES.get(country.value or "", "")
        current = (phone.value or "").strip()
        if code and (not current or current in COUNTRY_CODES.values()):
            phone.value = code
            phone.update()
    country.on_change = country_changed
    phone.value = COUNTRY_CODES["Kenya"]

    def collect() -> dict[str, str]:
        return {
            "username": (username.value or "").strip(), "full_name": (full_name.value or "").strip(),
            "email": (email.value or "").strip(), "phone": (phone.value or "").strip(),
            "password": password.value or "", "confirm_password": confirm.value or "",
            "role": next(iter(role.selected), ""), "country": country.value or "",
            "region": (region.value or "").strip(),
        }

    def show_errors(errors: dict[str, str]) -> None:
        for name, control in fields.items():
            control.error_text = errors.get(name)
        role_error.value = errors.get("role", "")
        role_error.visible = "role" in errors

    def submit(e: ft.ControlEvent) -> None:
        form_error.visible = False
        data = collect()
        errors = validate_registration(data)
        show_errors(errors)
        if errors:
            form_error.value = tr("register.fix_errors", "Please fix the highlighted fields.")
            form_error.visible = True
            page.update()
            return
        create_btn.disabled = True
        page.update()
        ok, message = register_user(data)
        create_btn.disabled = False
        if ok:
            session.data["prefill_username"] = data["username"]
            show_snack(page, tr("register.success", "Account created! Please log in."))
            page.go("/login")
            return
        lowered = message.lower()
        if "username" in lowered:
            username.error_text = message
        elif "email" in lowered:
            email.error_text = message
        else:
            form_error.value = message
            form_error.visible = True
        page.update()

    create_btn = ft.FilledButton(
        tr("register.button", "Create account"), on_click=submit, height=fs(50),
        style=ft.ButtonStyle(bgcolor=PRIMARY, color=theme.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
    )
    region.on_submit = submit

    card = ft.Container(
        col={"xs": 12, "sm": 10, "md": 8, "lg": 6, "xl": 5},  # full width on phones, capped on desktop
        padding=20,
        bgcolor=pal.card,
        border_radius=RADIUS + 6,
        border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Text(tr("register.title", "Join AgriLink Africa"), size=fs(22), weight=ft.FontWeight.W_700, color=palette().text),
            ft.Text(tr("register.subtitle", "Sell your harvest or source crops directly from farmers."),
                    size=fs(13), color=pal.muted),
            ft.Text(tr("register.i_am", "I am a…"), size=fs(14), weight=ft.FontWeight.W_600, color=palette().text),
            role, role_error,
            username, full_name, email, phone,
            password, confirm, show_password,
            ft.Row([country]), region,
            form_error,
            create_btn,
            ft.Row([
                ft.Text(tr("register.have_account", "Already have an account?"), size=fs(14), color=pal.muted),
                ft.TextButton(tr("register.login_link", "Log in"), on_click=lambda e: page.go("/login")),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=0, wrap=True),
        ], spacing=12, tight=True),
    )

    return ft.View(
        route="/register",
        bgcolor=pal.bg,
        padding=PAD,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        appbar=ft.AppBar(title=ft.Text(tr("register.appbar", "Create account"), color=theme.WHITE),
                         bgcolor=PRIMARY, color=theme.WHITE),
        controls=[ft.ResponsiveRow([card], alignment=ft.MainAxisAlignment.CENTER)],
    )
