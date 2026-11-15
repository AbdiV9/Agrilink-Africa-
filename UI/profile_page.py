# Owner: Person 2 (Frontend Flet UI Lead)
"""Depop-style profile (/profile/<id>): avatar, name, location, stars, verified
badge, crops planted, listings grid, reviews and a "Get verified" form."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from Auth.session import session
from UI import components as c
from UI import mock_data as md
from UI.components import tr
from UI.theme import ACCENT, PRIMARY, RADIUS, crop_emoji, fs, palette

log = logging.getLogger(__name__)

DOC_TYPES = [
    ("land_tenure", "Land title / lease (land tenure)"),
    ("cooperative", "Cooperative membership ID"),
    ("gov_registration", "Government farmer registration"),
    ("subsidy_program", "Subsidy programme enrolment"),
    ("livestock", "Livestock ownership proof"),
]
STATUS_COLORS = {"pending": ACCENT, "approved": PRIMARY, "rejected": "#C62828"}


def _review_dialog(page: ft.Page, uid: int, seller: dict[str, Any], route: str) -> ft.AlertDialog:
    """Pick 1-5 stars and leave a comment."""
    rating = {"value": 5}
    stars = ft.Row(spacing=0, alignment=ft.MainAxisAlignment.CENTER)
    comment = ft.TextField(label=tr("profile.comment", "Comment (optional)"), multiline=True, min_lines=2,
                           max_lines=4, max_length=300)
    error = ft.Text("", color=palette(page).down, size=fs(12), visible=False)
    dlg = ft.AlertDialog(modal=True)

    def paint() -> None:
        stars.controls = [
            ft.IconButton(ft.Icons.STAR if i <= rating["value"] else ft.Icons.STAR_BORDER, icon_color=ACCENT,
                          icon_size=fs(32), on_click=lambda e, n=i: choose(n))
            for i in range(1, 6)
        ]

    def choose(n: int) -> None:
        rating["value"] = n
        paint()
        stars.update()

    def save(e: ft.ControlEvent) -> None:
        try:
            md.call("add_review", uid, seller["id"], rating["value"], (comment.value or "").strip())
        except ValueError as exc:
            error.value = str(exc)
            error.visible = True
            error.update()
            return
        page.close(dlg)
        c.show_snack(page, tr("profile.review_thanks", "Thanks for your review!"))
        page.go(route)

    paint()
    dlg.title = ft.Text(tr("profile.review_title", "Review {name}", name=seller.get("full_name") or seller["username"]), color=palette().text)
    dlg.content = ft.Column([stars, comment, error], tight=True, width=340, spacing=10)
    dlg.actions = [ft.TextButton(tr("common.cancel", "Cancel"), on_click=lambda e: page.close(dlg)),
                   ft.FilledButton(tr("profile.post_review", "Post review"), on_click=save)]
    return dlg


def _verification_card(page: ft.Page, uid: int, verified: bool, route: str) -> ft.Container:
    """'Get verified' form plus the status of past submissions."""
    pal = palette(page)
    try:
        submissions = md.call("get_verifications", uid)
    except Exception:
        submissions = []
    labels = dict(DOC_TYPES)
    history = [
        ft.Row([
            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=fs(16), color=pal.muted),
            ft.Text(f"{labels.get(s['doc_type'], s['doc_type'])} · {s['doc_reference']}", size=fs(12), expand=True, color=palette().text),
            ft.Container(ft.Text(s["status"].upper(), size=fs(10), color="white", weight=ft.FontWeight.W_700),
                         bgcolor=STATUS_COLORS.get(s["status"], pal.muted), border_radius=6,
                         padding=ft.padding.symmetric(2, 6)),
        ], spacing=6)
        for s in submissions
    ]
    if verified:
        return ft.Container(
            padding=14, border_radius=RADIUS, bgcolor=pal.chip_up_bg,
            content=ft.Column([
                ft.Row([c.verified_badge(22), ft.Text(tr("profile.is_verified", "You're a verified farmer"),
                                                       size=fs(15), weight=ft.FontWeight.W_700, color=palette().text)]),
                ft.Text(tr("profile.verified_sub", "Buyers see a ✔ next to your name on every listing."),
                        size=fs(12), color=pal.muted),
                *history,
            ], spacing=8),
        )

    doc_dd = ft.Dropdown(label=tr("profile.doc_type", "Document type"), expand=True,
                         options=[ft.dropdown.Option(k, tr(f"profile.doc_{k}", v)) for k, v in DOC_TYPES])
    ref = ft.TextField(label=tr("profile.doc_ref", "Reference / ID number"), hint_text="e.g. KE-COOP-NKR-0412")

    def submit(e: ft.ControlEvent) -> None:
        doc_dd.error_text = None if doc_dd.value else tr("profile.need_doc", "Choose a document type")
        ref.error_text = None if len((ref.value or "").strip()) >= 3 else tr("profile.need_ref", "Enter the reference number")
        if doc_dd.error_text or ref.error_text:
            page.update()
            return
        try:
            md.call("submit_verification", uid, doc_dd.value, (ref.value or "").strip())
        except ValueError as exc:
            ref.error_text = str(exc)
            page.update()
            return
        c.show_snack(page, tr("profile.submitted", "Submitted! We'll review it within 2 working days."))
        page.go(route)

    return ft.Container(
        padding=14, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.VERIFIED_OUTLINED, color=palette(page).info),
                    ft.Text(tr("profile.get_verified", "Get verified"), size=fs(16), weight=ft.FontWeight.W_700, color=palette().text)]),
            ft.Text(tr("profile.verify_why", "Verified farmers get a ✔ badge and sell up to 2× faster. "
                                             "Submit one of these documents:"), size=fs(13), color=pal.muted),
            ft.Row([doc_dd]),
            ref,
            ft.FilledButton(tr("profile.submit_doc", "Submit for review"), icon=ft.Icons.UPLOAD_FILE, on_click=submit),
            *history,
        ], spacing=10),
    )


def build_profile_view(page: ft.Page, user_id: int, **params: Any) -> ft.View:
    """Public profile; extra controls when it's your own."""
    pal = palette(page)
    route = f"/profile/{user_id}"
    me = int((session.user or md.MOCK_USER)["id"])
    profile = md.call("get_seller_profile", user_id)
    if profile is None:
        return c.app_view(page, route, tr("profile.title", "Profile"), controls=[
            c.empty_state(ft.Icons.PERSON_OFF, tr("profile.not_found", "Profile not found"), "",
                          tr("crop.back_market", "Back to market"), lambda e: page.go("/market"))])
    own = user_id == me
    name = profile.get("full_name") or profile["username"]
    initials = "".join(p[0] for p in name.split()[:2]).upper()
    listings = profile.get("listings", [])
    reviews = profile.get("reviews", [])

    # --- header ----------------------------------------------------------------
    name_row: list[ft.Control] = [ft.Text(name, size=fs(22), weight=ft.FontWeight.W_800, color=palette().text)]
    if profile.get("verified"):
        name_row.append(c.verified_badge(22))
    role_label = {"farmer": "🌾 Farmer", "buyer": "🛒 Buyer", "both": "🔁 Farmer & buyer"}.get(profile.get("role"), "")
    member_since = c.short_date(profile.get("created_at", "")) + " " + (profile.get("created_at") or "")[:4]

    def stat(value: str, label: str) -> ft.Column:
        return ft.Column([ft.Text(value, size=fs(18), weight=ft.FontWeight.W_800, color=palette().text),
                          ft.Text(label, size=fs(12), color=pal.muted)],
                         spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)

    if own:
        buttons = [ft.OutlinedButton(tr("profile.edit", "Edit profile"), icon=ft.Icons.EDIT,
                                     on_click=lambda e: page.go("/settings"), expand=True)]
    else:
        buttons = [
            ft.FilledButton(tr("profile.message", "Message"), icon=ft.Icons.CHAT_BUBBLE_OUTLINE, expand=True,
                            style=ft.ButtonStyle(bgcolor=PRIMARY, color="white"),
                            on_click=lambda e: page.go(f"/messages/{user_id}")),
            ft.OutlinedButton(tr("profile.review", "Leave a review"), icon=ft.Icons.STAR_BORDER, expand=True,
                              on_click=lambda e: page.open(_review_dialog(page, me, profile, route))),
        ]

    header = ft.Container(
        padding=16, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
        content=ft.Column([
            ft.Row([
                ft.CircleAvatar(content=ft.Text(initials, size=fs(26), weight=ft.FontWeight.W_700),
                                bgcolor=PRIMARY, color="white", radius=fs(40)),
                ft.Column([
                    ft.Row(name_row, spacing=6, wrap=True),
                    ft.Text(f"@{profile['username']}", size=fs(13), color=pal.muted),
                    ft.Row([ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=fs(15), color=pal.muted),
                            ft.Text(f"{profile.get('region') or ''}, {profile.get('country') or ''}".strip(", "),
                                    size=fs(13), color=pal.muted)], spacing=2),
                    c.star_rating(profile.get("avg_rating"), profile.get("review_count", 0), size=15),
                ], spacing=3, expand=True),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Row([
                ft.Container(ft.Text(role_label, size=fs(12), color=palette().text), bgcolor=pal.card_alt, border_radius=12,
                             padding=ft.padding.symmetric(4, 10)),
                ft.Text(tr("profile.member_since", "Member since {d}", d=member_since.strip()), size=fs(12),
                        color=pal.muted),
            ], spacing=10, wrap=True),
            ft.Row([stat(str(len(listings)), tr("profile.listings", "Listings")),
                    stat(str(profile.get("review_count", 0)), tr("profile.reviews", "Reviews")),
                    stat(f"{profile.get('avg_rating', 0):.1f}", tr("profile.rating", "Rating"))]),
            ft.Row(buttons, spacing=10),
        ], spacing=12),
    )

    # --- crops planted -----------------------------------------------------------
    planted: list[ft.Control] = []
    if profile.get("role") in ("farmer", "both"):
        try:
            plantings = md.call("get_plantings", user_id)
        except Exception:
            plantings = []
        if plantings:
            planted = [
                c.section_title(tr("profile.planted", "Crops planted")),
                ft.Row([
                    ft.Container(
                        padding=ft.padding.symmetric(6, 12), border_radius=20, bgcolor=pal.card_alt,
                        content=ft.Text(f"{crop_emoji(p['crop_name'])} {p['crop_name']} · "
                                        + tr("profile.harvest_on", "harvest {d}", d=c.short_date(p["expected_harvest"] or "")),
                                        size=fs(12), color=palette().text),
                    ) for p in plantings
                ], wrap=True, spacing=8, run_spacing=8),
            ]

    # --- listings / reviews switcher ------------------------------------------------
    content_box = ft.Container()

    def listings_grid() -> ft.Control:
        if not listings:
            return c.empty_state(ft.Icons.STOREFRONT, tr("profile.no_listings", "No active listings"),
                                 "", tr("home.sell", "Sell crops") if own else None,
                                 (lambda e: page.go("/sell")) if own else None)
        return ft.ResponsiveRow([
            c.crop_card({**l, "seller_username": profile["username"], "seller_verified": profile.get("verified")},
                        on_click=lambda l: page.go(f"/listing/{l['id']}"))
            for l in listings], spacing=10, run_spacing=10)

    def reviews_list() -> ft.Control:
        if not reviews:
            return c.empty_state(ft.Icons.RATE_REVIEW_OUTLINED, tr("profile.no_reviews", "No reviews yet"))
        return ft.Column([
            ft.Container(
                padding=12, border_radius=RADIUS, bgcolor=pal.card, border=ft.border.all(1, pal.border),
                content=ft.Column([
                    ft.Row([c.star_rating(r["rating"], size=14),
                            ft.Text(c.short_date(r.get("created_at", "")), size=fs(11), color=pal.muted)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(r.get("comment") or "", size=fs(14), color=palette().text),
                    ft.TextButton(f"@{r.get('reviewer_username', '')}",
                                  on_click=lambda e, rid=r["reviewer_id"]: page.go(f"/profile/{rid}")),
                ], spacing=4),
            ) for r in reviews], spacing=8)

    def switch(e: ft.ControlEvent | None = None) -> None:
        which = next(iter(selector.selected))
        content_box.content = listings_grid() if which == "listings" else reviews_list()
        if e is not None:
            content_box.update()

    selector = ft.SegmentedButton(
        segments=[ft.Segment(value="listings", label=ft.Text(tr("profile.tab_listings", "Listings ({n})", n=len(listings)), color=palette().text)),
                  ft.Segment(value="reviews", label=ft.Text(tr("profile.tab_reviews", "Reviews ({n})", n=len(reviews)), color=palette().text))],
        selected={"listings"}, show_selected_icon=False, on_change=switch,
    )
    switch()

    extras: list[ft.Control] = []
    if own and profile.get("role") in ("farmer", "both"):
        extras = [_verification_card(page, user_id, bool(profile.get("verified")), route)]

    return c.app_view(page, route, tr("profile.title", "Profile") if not own else tr("profile.mine", "My profile"),
                      controls=[header, *extras, *planted, ft.Row([selector], scroll=ft.ScrollMode.AUTO),
                                content_box, ft.Container(height=8)])
