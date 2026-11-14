"""Login screen (/login)."""

from __future__ import annotations

import flet as ft

from Auth.auth import login_user
from Auth.session import session
from UI import theme
from UI.components import tr
from UI.theme import ACCENT, PAD, PRIMARY, RADIUS, fs, palette


def build_login_view(page: ft.Page, **params: object) -> ft.View:
    """Username + password form with inline errors and a link to register."""
    pal = palette(page)
    prefill = session.data.pop("prefill_username", "")

    username = ft.TextField(
        label=tr("login.username", "Username"), value=prefill, prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=not prefill, text_size=fs(15), border_radius=12, autocorrect=False,
    )
    password = ft.TextField(
        label=tr("login.password", "Password"), password=True, can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_OUTLINE, autofocus=bool(prefill), text_size=fs(15), border_radius=12,
    )
    error = ft.Text("", color=pal.down, size=fs(13), visible=False)
    spinner = ft.ProgressRing(width=20, height=20, stroke_width=2, color=theme.WHITE, visible=False)
    button_label = ft.Text(tr("login.button", "Log in"), size=fs(16), weight=ft.FontWeight.W_600)
    button = ft.FilledButton(
        content=ft.Row([spinner, button_label], alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=10),
        height=50,
        style=ft.ButtonStyle(bgcolor=PRIMARY, color=theme.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
    )

    def set_busy(busy: bool) -> None:
        spinner.visible = busy
        button.disabled = busy
        page.update()

    def submit(e: ft.ControlEvent) -> None:
        username.error_text = None
        password.error_text = None
        error.visible = False
        if not (username.value or "").strip():
            username.error_text = tr("login.need_username", "Enter your username")
        if not password.value:
            password.error_text = tr("login.need_password", "Enter your password")
        if username.error_text or password.error_text:
            page.update()
            return
        set_busy(True)
        ok, result = login_user(username.value or "", password.value or "")
        if ok:
            page.go("/home")
            return
        error.value = str(result)
        error.visible = True
        password.value = ""
        set_busy(False)

    button.on_click = submit
    password.on_submit = submit
    username.on_submit = lambda e: password.focus()

    card = ft.Container(
        width=420,
        padding=24,
        bgcolor=pal.card,
        border_radius=RADIUS + 6,
        border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Text(tr("login.title", "Welcome back"), size=fs(22), weight=ft.FontWeight.W_700),
            ft.Text(tr("login.subtitle", "Log in to buy, sell and track crop prices."), size=fs(13), color=pal.muted),
            ft.Container(height=4),
            username,
            password,
            error,
            button,
            ft.Row([
                ft.Text(tr("login.no_account", "New to AgriLink?"), size=fs(14), color=pal.muted),
                ft.TextButton(tr("login.register_link", "Create an account"), on_click=lambda e: page.go("/register")),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=0, wrap=True),
            ft.Container(
                padding=10, border_radius=10, bgcolor=pal.card_alt,
                content=ft.Text(tr("login.demo_hint", "Demo account: amina_w / Password123!"),
                                size=fs(12), color=pal.muted, text_align=ft.TextAlign.CENTER),
            ),
        ], spacing=12, tight=True),
    )

    hero = ft.Container(
        padding=ft.padding.only(top=40, bottom=24),
        content=ft.Column([
            ft.Container(
                width=76, height=76, border_radius=38, bgcolor=PRIMARY, alignment=ft.alignment.center,
                content=ft.Icon(ft.Icons.ECO, color=ACCENT, size=44),
            ),
            ft.Text("AgriLink Africa", size=fs(28), weight=ft.FontWeight.W_800, color=PRIMARY if not theme.is_dark(page) else pal.up),
            ft.Text(tr("login.tagline", "Fair prices, from farm to market."), size=fs(14), color=pal.muted),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
    )

    return ft.View(
        route="/login",
        bgcolor=pal.bg,
        padding=PAD,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[hero, card],
    )
