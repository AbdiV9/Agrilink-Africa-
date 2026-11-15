# Owner: Person 2 (Frontend Flet UI Lead)
"""Messages: inbox (/messages) and a conversation thread (/messages/<user_id>)
with a send box and a "send as SMS" toggle."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, fs, palette

log = logging.getLogger(__name__)


def _when(ts: str | None) -> str:
    """'14:05' for today, '12 Nov' otherwise."""
    if not ts:
        return ""
    try:
        moment = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    return moment.strftime("%H:%M") if moment.date() == datetime.now().date() else moment.strftime("%d %b").lstrip("0")


def _initials(name: str) -> str:
    return "".join(p[0] for p in (name or "?").split()[:2]).upper() or "?"


def _inbox(page: ft.Page, uid: int) -> ft.View:
    pal = palette(page)
    try:
        convos = md.call("get_conversations", uid)
        error = None
    except Exception:
        log.exception("get_conversations failed")
        convos, error = [], c.error_banner(tr("messages.load_error", "Couldn't load your messages."),
                                           on_retry=lambda e: page.go("/messages"))

    rows: list[ft.Control] = []
    for cv in convos:
        name = cv.get("other_full_name") or cv["other_username"]
        unread = int(cv.get("unread_count") or 0)
        preview = ("You: " if cv.get("last_sender_id") == uid else "") + (cv.get("last_body") or "")
        title: list[ft.Control] = [ft.Text(name, size=fs(15), weight=ft.FontWeight.W_700 if unread else ft.FontWeight.W_500,
                                           max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True, color=palette().text)]
        if cv.get("other_verified"):
            title.insert(1, c.verified_badge(15))
        rows.append(ft.Container(
            padding=12, border_radius=RADIUS, bgcolor=pal.card, ink=True,
            on_click=lambda e, oid=cv["other_id"]: page.go(f"/messages/{oid}"),
            content=ft.Row([
                ft.CircleAvatar(content=ft.Text(_initials(name), size=fs(15)), bgcolor=PRIMARY, color="white", radius=fs(22)),
                ft.Column([
                    ft.Row(title, spacing=4),
                    ft.Text(preview, size=fs(13), color=pal.text if unread else pal.muted, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, expand=True),
                ft.Column([
                    ft.Text(_when(cv.get("last_at")), size=fs(11), color=pal.muted),
                    ft.Container(ft.Text(str(unread), size=fs(11), color="#1B1F1C", weight=ft.FontWeight.W_700),
                                 bgcolor=ACCENT, border_radius=10, padding=ft.padding.symmetric(1, 7),
                                 visible=unread > 0),
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=12),
        ))
    if not rows and not error:
        rows.append(c.empty_state(ft.Icons.CHAT_BUBBLE_OUTLINE, tr("messages.empty", "No messages yet"),
                                  tr("messages.empty_sub", "Message a seller from any listing to start a conversation."),
                                  tr("home.browse", "Browse market"), lambda e: page.go("/market")))
    total_unread = sum(int(cv.get("unread_count") or 0) for cv in convos)
    return c.app_view(page, "/messages", tr("messages.title", "Messages"), nav="/messages", unread=total_unread,
                      actions=[ft.IconButton(ft.Icons.REFRESH, icon_color="white", tooltip=tr("common.refresh", "Refresh"),
                                             on_click=lambda e: page.go("/messages"))],
                      controls=[*([error] if error else []), *rows])


def _bubble(page: ft.Page, msg: dict[str, Any], mine: bool) -> ft.Row:
    pal = palette(page)
    via = msg.get("channel", "app")
    meta = _when(msg.get("created_at")) + (f" · {via.upper()}" if via != "app" else "")
    bubble = ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=ft.border_radius.only(top_left=16, top_right=16, bottom_left=4 if not mine else 16,
                                            bottom_right=4 if mine else 16),
        bgcolor=PRIMARY if mine else pal.card,
        border=None if mine else ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Text(msg.get("body", ""), size=fs(14), color="white" if mine else pal.text, selectable=True),
            ft.Row([
                *([ft.Icon(ft.Icons.SMS_OUTLINED, size=fs(12), color="#FFFFFF" if mine else pal.muted)] if via == "sms" else []),
                ft.Text(meta, size=fs(10), color="#FFFFFF" if mine else pal.muted),
            ], spacing=3, tight=True, alignment=ft.MainAxisAlignment.END),
        ], spacing=2, tight=True, horizontal_alignment=ft.CrossAxisAlignment.END),
    )
    return ft.Row([ft.Container(bubble, width=None, expand=False)],
                  alignment=ft.MainAxisAlignment.END if mine else ft.MainAxisAlignment.START,
                  wrap=False)


def _thread(page: ft.Page, uid: int, other_id: int) -> ft.View:
    pal = palette(page)
    route = f"/messages/{other_id}"
    try:
        other = md.call("get_user_by_id", other_id)
    except Exception:
        other = None
    if other is None or other_id == uid:
        return c.app_view(page, route, tr("messages.title", "Messages"), controls=[
            c.empty_state(ft.Icons.PERSON_OFF, tr("messages.no_user", "This person isn't on AgriLink"), "",
                          tr("messages.back", "Back to messages"), lambda e: page.go("/messages"))])
    name = other.get("full_name") or other["username"]

    try:
        md.call("mark_read", uid, other_id)
    except Exception:
        log.exception("mark_read failed")

    history = ft.ListView(expand=True, spacing=6, auto_scroll=True, padding=ft.padding.only(bottom=8))

    def load_thread() -> None:
        try:
            msgs = md.call("get_thread", uid, other_id)
        except Exception:
            log.exception("get_thread failed")
            history.controls = [c.error_banner(tr("messages.thread_error", "Couldn't load this conversation."))]
            return
        history.controls = [_bubble(page, m, m["sender_id"] == uid) for m in msgs] or [
            c.empty_state(ft.Icons.WAVING_HAND, tr("messages.say_hi", "Say hello to {name}", name=name.split()[0]))]

    load_thread()

    draft = session.data.get("message_draft") or {}
    listing_id = draft.get("listing_id") if draft.get("user_id") == other_id else None
    box = ft.TextField(
        hint_text=tr("messages.type", "Type a message…"), multiline=True, min_lines=1, max_lines=5,
        shift_enter=True, expand=True, border_radius=22, filled=True, dense=True, text_size=fs(14),
        value=draft.get("text", "") if draft.get("user_id") == other_id else "",
    )
    sms_toggle = ft.Switch(label=tr("messages.as_sms", "Send as SMS"), value=False, active_color=ACCENT,
                           label_style=ft.TextStyle(size=fs(12)))
    send_btn = ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color="white", bgcolor=PRIMARY,
                             tooltip=tr("messages.send", "Send"))
    status = ft.Text("", size=fs(11), color=pal.muted, visible=False)

    def send(e: ft.ControlEvent) -> None:
        body = (box.value or "").strip()
        if not body:
            return
        channel = "sms" if sms_toggle.value else "app"
        send_btn.disabled = True
        page.update()
        try:
            md.call("send_message", uid, other_id, body, listing_id=listing_id, channel=channel)
        except ValueError as exc:
            c.show_snack(page, str(exc), error=True)
            send_btn.disabled = False
            page.update()
            return
        except Exception:
            log.exception("send_message failed")
            c.show_snack(page, tr("messages.send_error", "Message not sent. Please try again."), error=True)
            send_btn.disabled = False
            page.update()
            return
        if channel == "sms":
            try:
                ok, note = md.call("send_sms", other.get("phone") or "", body)
            except Exception:
                ok, note = False, tr("messages.sms_failed", "SMS couldn't be sent, but the in-app message was delivered.")
            status.value = note
            status.color = pal.muted if ok else pal.down
            status.visible = True
        session.data.pop("message_draft", None)
        box.value = ""
        send_btn.disabled = False
        load_thread()
        page.update()
        box.focus()

    send_btn.on_click = send
    box.on_submit = send

    title = ft.GestureDetector(
        on_tap=lambda e: page.go(f"/profile/{other_id}"),
        mouse_cursor=ft.MouseCursor.CLICK,
        content=ft.Row([
            ft.CircleAvatar(content=ft.Text(_initials(name), size=fs(12)), bgcolor=ACCENT, color="#1B1F1C", radius=16),
            ft.Text(name, size=fs(18), weight=ft.FontWeight.W_700, color="white"),
            *([c.verified_badge(16)] if other.get("verified") else []),
        ], spacing=8, tight=True),
    )
    composer = ft.Container(
        padding=ft.padding.only(top=6),
        border=ft.border.only(top=ft.BorderSide(1, pal.border)),
        content=ft.Column([
            ft.Row([box, send_btn], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([sms_toggle, status], spacing=8, wrap=True),
        ], spacing=4, tight=True),
    )
    view = c.app_view(page, route, name, scroll=False, controls=[history, composer])
    view.appbar.title = title
    return view


def build_messages_view(page: ft.Page, user_id: int | None = None, **params: Any) -> ft.View:
    """Inbox when ``user_id`` is None, otherwise the thread with that user."""
    uid = int((session.user or md.MOCK_USER)["id"])
    if user_id is None:
        return _inbox(page, uid)
    return _thread(page, uid, int(user_id))
