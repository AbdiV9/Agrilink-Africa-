# Owner: Person 2 (Frontend Flet UI Lead)
"""AI assistant (/chatbot): chat bubbles, preset prompt buttons, typing indicator."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

import config
from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)

PRESET_PROMPTS = [
    ("chat.p_plant", "What should I plant this month?", ft.Icons.GRASS),
    ("chat.p_sell_maize", "Best time to sell my maize?", ft.Icons.SCHEDULE),
    ("chat.p_trend", "Explain this price trend", ft.Icons.SHOW_CHART),
    ("chat.p_tomatoes", "Find cheapest tomatoes near me", ft.Icons.SEARCH),
    ("chat.p_summary", "Summarise today's market", ft.Icons.SUMMARIZE),
]
HISTORY_KEY = "chat_history"   # session.data list of {"role": "user"|"assistant", "text": str}
MAX_CONTEXT_TURNS = 8


def _bubble(page: ft.Page, role: str, text: str) -> ft.Row:
    pal = palette(page)
    mine = role == "user"
    body: ft.Control
    if mine:
        body = ft.Text(text, size=fs(14), color="white", selectable=True)
    else:
        body = ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                           md_style_sheet=c.markdown_style(14))
    bubble = ft.Container(
        content=body,
        padding=ft.padding.symmetric(horizontal=12, vertical=9),
        bgcolor=PRIMARY if mine else pal.card,
        border=None if mine else ft.border.all(1, pal.border),
        border_radius=ft.border_radius.only(top_left=16, top_right=16, bottom_left=16 if mine else 4,
                                            bottom_right=4 if mine else 16),
        expand=not mine,
    )
    avatar = ft.CircleAvatar(content=ft.Icon(ft.Icons.ECO, size=fs(16), color=PRIMARY), bgcolor=ACCENT, radius=15)
    controls = [bubble] if mine else [avatar, bubble]
    return ft.Row(controls, alignment=ft.MainAxisAlignment.END if mine else ft.MainAxisAlignment.START,
                  vertical_alignment=ft.CrossAxisAlignment.START, spacing=8)


def build_chatbot_view(page: ft.Page, **params: Any) -> ft.View:
    """Chat with the AgriLink assistant."""
    pal = palette(page)
    user = session.user or md.MOCK_USER
    history: list[dict[str, str]] = session.data.setdefault(HISTORY_KEY, [])

    chat = ft.ListView(expand=True, spacing=10, auto_scroll=True, padding=ft.padding.only(bottom=8))
    typing = ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2, color=PRIMARY),
                     ft.Text(tr("chat.thinking", "AgriLink AI is thinking…"), size=fs(12), color=pal.muted)],
                    visible=False, spacing=8)
    box = ft.TextField(hint_text=tr("chat.ask", "Ask about crops, prices or weather…"), expand=True,
                       multiline=True, min_lines=1, max_lines=4, shift_enter=True, border_radius=22, filled=True,
                       dense=True, text_size=fs(14), value=session.data.pop("chatbot_prefill", ""))
    send_btn = ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color="white", bgcolor=PRIMARY,
                             tooltip=tr("messages.send", "Send"))
    welcome = tr("chat.welcome",
                 "Hi {name}! 👋 I'm your farming assistant. Ask me what to plant, when to sell, or what prices "
                 "are doing in {region}. Tap a suggestion below to start.",
                 name=(user.get("full_name") or user["username"]).split()[0], region=user.get("region") or "your area")

    def render(update: bool = True) -> None:
        chat.controls = [_bubble(page, "assistant", welcome)] + [_bubble(page, m["role"], m["text"]) for m in history]
        if update:
            chat.update()

    def set_busy(busy: bool) -> None:
        typing.visible = busy
        send_btn.disabled = busy
        box.disabled = busy
        for chip in presets.controls:
            chip.disabled = busy
        page.update()

    def ask(question: str) -> None:
        question = question.strip()
        if not question or send_btn.disabled:
            return
        history.append({"role": "user", "text": question})
        box.value = ""
        render()
        set_busy(True)

        def worker() -> None:
            context = {"history": history[-MAX_CONTEXT_TURNS * 2:-1]}
            try:
                answer = md.call("ask", user, question, context=context)
            except Exception:
                log.exception("chatbot.ask failed")
                answer = tr("chat.error", "Sorry, I couldn't answer that right now. Please try again in a moment.")
            history.append({"role": "assistant", "text": answer or "…"})
            try:
                render()
                set_busy(False)
                box.focus()
            except Exception:  # user left the page while waiting
                pass

        page.run_thread(worker)

    send_btn.on_click = lambda e: ask(box.value or "")
    box.on_submit = lambda e: ask(box.value or "")

    presets = ft.Row(
        [ft.OutlinedButton(tr(key, text), icon=icon, on_click=lambda e, q=text, k=key: ask(tr(k, q)),
                           style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20),
                                                padding=ft.padding.symmetric(horizontal=12, vertical=6)))
         for key, text, icon in PRESET_PROMPTS],
        scroll=ft.ScrollMode.AUTO, spacing=8,
    )

    def clear(e: ft.ControlEvent) -> None:
        history.clear()
        render()

    offline_note: list[ft.Control] = []
    if not config.AI_ENABLED:
        offline_note = [ft.Container(
            padding=10, border_radius=RADIUS, bgcolor=pal.card_alt,
            content=ft.Row([ft.Icon(ft.Icons.CLOUD_OFF, size=fs(16), color=pal.muted),
                            ft.Text(tr("chat.offline", "Offline demo mode: add an AI key to .env for live answers."),
                                    size=fs(12), color=pal.muted, expand=True)]),
        )]

    render(update=False)
    composer = ft.Container(
        padding=ft.padding.only(top=6),
        border=ft.border.only(top=ft.BorderSide(1, pal.border)),
        content=ft.Column([typing, presets, ft.Row([box, send_btn], spacing=8,
                                                   vertical_alignment=ft.CrossAxisAlignment.END)],
                          spacing=8, tight=True),
    )
    return c.app_view(
        page, "/chatbot", tr("chat.title", "AgriLink AI"), scroll=False,
        actions=[ft.IconButton(ft.Icons.DELETE_SWEEP_OUTLINED, icon_color="white",
                               tooltip=tr("chat.clear", "Clear chat"), on_click=clear)],
        controls=[*offline_note, chat, composer],
    )
