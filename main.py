# Owner: Person 3 (Integration, Logic & API Lead)
"""AgriLink Africa entry point: database start-up, routing and route guards.

Run with:  python main.py      (or  flet run main.py)

Routing
-------
Every page lives in ``UI/<name>_page.py`` and exposes
``build_<name>_view(page: ft.Page, **params) -> ft.View``. Pages are
imported lazily, so a page that isn't built yet (or crashes while
building) shows a friendly placeholder instead of taking the app down.
"""

from __future__ import annotations

import importlib
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

import flet as ft

import config
from Auth.session import session
from Databases.Database_Setup import setup_database

log = logging.getLogger("agrilink.main")

PRIMARY = "#2E7D32"
PUBLIC_ROUTES = {"login", "register"}


@dataclass(frozen=True)
class PageSpec:
    """Where to find a page builder and which route it hangs under for 'back'."""

    module: str
    builder: str
    title: str
    parent: str | None = None  # route shown underneath, so the back arrow works
    param: str | None = None   # name of the id kwarg passed to the builder


PAGES: dict[str, PageSpec] = {
    "login":    PageSpec("UI.login_page", "build_login_view", "Log in"),
    "register": PageSpec("UI.register_page", "build_register_view", "Create account", parent="/login"),
    "home":     PageSpec("UI.home_page", "build_home_view", "Home"),
    "market":   PageSpec("UI.market_page", "build_market_view", "Market"),
    "crop":     PageSpec("UI.crop_detail_page", "build_crop_detail_view", "Crop prices", "/market", "crop_id"),
    "listing":  PageSpec("UI.listing_page", "build_listing_view", "Listing", "/market", "listing_id"),
    "sell":     PageSpec("UI.sell_page", "build_sell_view", "Sell"),
    "messages": PageSpec("UI.messages_page", "build_messages_view", "Messages", None, "user_id"),
    "chatbot":  PageSpec("UI.chatbot_page", "build_chatbot_view", "AgriLink Assistant", "/home"),
    "profile":  PageSpec("UI.profile_page", "build_profile_view", "Profile", "/market", "user_id"),
    "settings": PageSpec("UI.settings_page", "build_settings_view", "Settings"),
    # STRETCH
    "news":      PageSpec("UI.news_page", "build_news_view", "Farming news", "/home"),
    "purchases": PageSpec("UI.purchases_page", "build_purchases_view", "Purchase history", "/settings"),
}


@dataclass
class ParsedRoute:
    """Result of parsing a route string."""

    name: str | None
    params: dict[str, Any] = field(default_factory=dict)


def parse_route(route: str) -> ParsedRoute:
    """Turn '/crop/3' into ParsedRoute('crop', {'crop_id': 3}).

    Unknown routes or non-numeric ids give ``name=None``. '/' means home.
    """
    path = (route or "/").split("?", 1)[0].strip("/")
    if not path:
        return ParsedRoute("home")
    parts = path.split("/")
    name, rest = parts[0], parts[1:]
    spec = PAGES.get(name)
    if spec is None or len(rest) > 1:
        return ParsedRoute(None)
    if not rest:
        # /crop, /listing and /profile need an id; /messages works without one.
        if spec.param and name != "messages":
            return ParsedRoute(None)
        return ParsedRoute(name)
    if spec.param is None or not rest[0].isdigit():
        return ParsedRoute(None)
    return ParsedRoute(name, {spec.param: int(rest[0])})


# --------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------
_applied_prefs: tuple[Any, ...] | None = None


def apply_user_preferences(page: ft.Page, force: bool = False) -> None:
    """Apply the logged-in user's dark mode and text size (once per change)."""
    global _applied_prefs
    user = session.user or {}
    prefs = (bool(user.get("dark_mode")), float(user.get("text_scale") or 1.0))
    if prefs == _applied_prefs and not force:
        return
    _applied_prefs = prefs
    try:
        from UI.theme import apply_theme  # Phase 3

        apply_theme(page, dark=prefs[0], text_scale=prefs[1])
    except ImportError:
        page.theme = ft.Theme(color_scheme_seed=PRIMARY)
        page.dark_theme = ft.Theme(color_scheme_seed=PRIMARY)
        page.theme_mode = ft.ThemeMode.DARK if prefs[0] else ft.ThemeMode.LIGHT


def _start_background_jobs(page: ft.Page) -> None:
    """Start notification checks once per login (Phase 5 provides the loop)."""
    if session.data.get("jobs_started"):
        return
    session.data["jobs_started"] = True
    try:
        from Auth import notifications

        starter: Callable[[ft.Page], None] | None = getattr(notifications, "start_notification_loop", None)
        if starter:
            starter(page)
    except ImportError:
        log.debug("Notifications not built yet; skipping background checks.")
    except Exception:
        log.exception("Could not start background notifications")


# --------------------------------------------------------------------------
# Fallback views
# --------------------------------------------------------------------------
def _fallback_nav(page: ft.Page, route: str) -> ft.NavigationBar:
    """Plain nav bar used only by placeholder views (real pages use UI.components)."""
    tabs = [("/home", ft.Icons.HOME, "Home"), ("/market", ft.Icons.STOREFRONT, "Market"),
            ("/sell", ft.Icons.ADD_BOX, "Sell"), ("/messages", ft.Icons.CHAT, "Messages"),
            ("/settings", ft.Icons.SETTINGS, "Settings")]
    selected = next((i for i, t in enumerate(tabs) if route.startswith(t[0])), 0)
    return ft.NavigationBar(
        selected_index=selected,
        destinations=[ft.NavigationBarDestination(icon=icon, label=label) for _, icon, label in tabs],
        on_change=lambda e: page.go(tabs[e.control.selected_index][0]),
    )


def _placeholder_view(page: ft.Page, route: str, title: str, message: str, icon: str) -> ft.View:
    """Simple centred message view (coming soon / not found / error)."""
    return ft.View(
        route=route,
        appbar=ft.AppBar(title=ft.Text(title), bgcolor=PRIMARY, color="white"),
        navigation_bar=_fallback_nav(page, route) if session.is_logged_in() else None,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(icon, size=64, color=PRIMARY),
            ft.Text(message, text_align=ft.TextAlign.CENTER, size=16),
            ft.FilledButton("Go to Home" if session.is_logged_in() else "Go to Login",
                            on_click=lambda _: page.go("/home" if session.is_logged_in() else "/login")),
        ],
    )


def build_view(page: ft.Page, route: str) -> ft.View:
    """Build the view for a route, falling back to a placeholder on any problem."""
    parsed = parse_route(route)
    if parsed.name is None:
        return _placeholder_view(page, route, "Not found", "We couldn't find that page.", ft.Icons.SEARCH_OFF)
    spec = PAGES[parsed.name]
    try:
        module = importlib.import_module(spec.module)
        builder = getattr(module, spec.builder)
    except (ImportError, AttributeError):
        return _placeholder_view(page, route, spec.title, f"The {spec.title} page is coming soon.",
                                 ft.Icons.CONSTRUCTION)
    try:
        view = builder(page, **parsed.params)
        view.route = route
        return view
    except Exception as exc:  # a page bug should never crash the whole app
        log.error("Error building %s:\n%s", route, traceback.format_exc())
        detail = f"\n\n{exc}" if config.DEBUG else ""
        return _placeholder_view(page, route, spec.title, f"Sorry, this page hit a problem.{detail}",
                                 ft.Icons.ERROR_OUTLINE)


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
def main(page: ft.Page) -> None:
    """Flet entry point."""
    page.title = config.APP_NAME
    page.padding = 0
    try:  # desktop window: start at phone size, still resizable for desktop layout
        page.window.width = 430
        page.window.height = 860
        page.window.min_width = 360
    except AttributeError:
        pass
    apply_user_preferences(page, force=True)

    try:
        if setup_database():
            log.info("Created and seeded a new database.")
    except Exception:
        log.exception("Database start-up failed")
        page.views.append(_placeholder_view(page, "/", "Database error",
                                            "The database could not be opened. Check the logs.",
                                            ft.Icons.STORAGE))
        page.update()
        return

    def route_change(e: ft.RouteChangeEvent | None = None) -> None:
        route = page.route or "/"
        name = parse_route(route).name

        # Route guards
        if not session.is_logged_in() and name not in PUBLIC_ROUTES:
            if route != "/login":
                page.go("/login")
                return
        if session.is_logged_in() and name in PUBLIC_ROUTES:
            page.go("/home")
            return
        if session.is_logged_in():
            apply_user_preferences(page)
            _start_background_jobs(page)
        else:
            session.data.pop("jobs_started", None)

        page.views.clear()
        spec = PAGES.get(name or "")
        parent = spec.parent if spec else None
        if name == "messages" and parse_route(route).params:
            parent = "/messages"  # thread view sits on top of the inbox
        if parent:
            page.views.append(build_view(page, parent))
        page.views.append(build_view(page, route))
        page.update()

    def view_pop(e: ft.ViewPopEvent) -> None:
        if len(page.views) > 1:
            page.views.pop()
            page.go(page.views[-1].route or "/home")
        else:
            page.go("/home")

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    log.info("Features enabled: %s", config.feature_summary())
    page.go(page.route or "/login")


if __name__ == "__main__":
    ft.app(target=main, assets_dir=config.ASSETS_DIR)
