# Owner: Person 2 (Frontend Flet UI Lead)
"""Launch any single page (or a gallery of all components) for quick UI work.

Run from the project root::

    python -m UI.preview components            # every component, mock data
    python -m UI.preview market --mock         # Market page with mock data
    python -m UI.preview crop/1                # Crop page using the real DB
    python -m UI.preview home --dark --scale 1.3
    python -m UI.preview login --web           # open in a browser instead

You're auto-logged in (as amina_w), except on login/register, so route
guards don't bounce you. Navigation still works, because pages are served
through main.py's router.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import flet as ft

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from Auth.session import session  # noqa: E402
from UI import components as c  # noqa: E402
from UI import mock_data as md  # noqa: E402
from UI.theme import apply_theme  # noqa: E402


def build_components_gallery(page: ft.Page) -> ft.View:
    """One scrolling page showing every component with mock data."""
    crops = md.MOCK_CROPS
    history = md.MOCKS["get_price_history"](1, 365)
    latest = md.MOCKS["get_latest_price"](1)
    chart = c.price_chart(history, md.MOCKS["predict_price"](1, 30), initial_range="3M")
    listings = md.MOCKS["search_listings"]()[:4]
    results = ft.Text("Search filters will appear here", size=12)

    def on_search(filters: dict) -> None:
        results.value = f"on_search({filters})"
        results.update()

    def toggle_prediction(e: ft.ControlEvent) -> None:
        chart.toggle_prediction(e.control.value)

    def toggle_dark(e: ft.ControlEvent) -> None:
        apply_theme(page, dark=e.control.value, text_scale=1.0)
        page.views.clear()
        page.views.append(build_components_gallery(page))
        page.update()

    return c.app_view(page, "/components", "Components", nav="/home", unread=3, controls=[
        ft.Row([ft.Text("Dark mode"), ft.Switch(value=page.theme_mode == ft.ThemeMode.DARK, on_change=toggle_dark)]),
        c.section_title("price_header + price_chart"),
        c.price_header("Maize", latest["price"], latest["change_pct"], page=page),
        chart,
        ft.Row([ft.Switch(label="Show AI prediction", on_change=toggle_prediction)]),
        c.section_title("search_bar_with_filters"),
        c.search_bar_with_filters(page, crops, on_search),
        results,
        c.section_title("crop_card grid", "See all", lambda e: None),
        ft.ResponsiveRow([c.crop_card(l, on_click=lambda l: c.show_snack(page, f"Open listing {l['id']}"),
                                      hearted=i == 0) for i, l in enumerate(listings)], spacing=10, run_spacing=10),
        c.section_title("weather_card"),
        c.weather_card(md.MOCKS["get_forecast_for_region"]("Nakuru"), page),
        c.weather_card(None, page),
        c.section_title("alert_tile"),
        c.alert_tile("Maize is above KES 50", "Your alert target was hit", "price", on_dismiss=lambda e: None),
        c.alert_tile("Harvest maize in 5 days", "Planted 115 days ago · 2.5 acres", "harvest"),
        c.alert_tile("Long rains planting window opens", "Good time to plant beans", "season"),
        c.section_title("sparkline, change_chip, star_rating, verified_badge"),
        ft.Row([c.sparkline([p["price"] for p in history[-30:]]), c.change_chip(2.4, page),
                c.change_chip(-1.3, page)], wrap=True),
        ft.Row([c.star_rating(4.5, 12), c.verified_badge(label=True)], wrap=True),
        c.section_title("states"),
        c.loading_spinner("Loading prices…"),
        c.error_banner("Couldn't load listings. Check your connection.", on_retry=lambda e: None),
        c.empty_state(ft.Icons.FAVORITE_BORDER, "No crops in your watchlist",
                      "Tap the heart on any crop to follow its price.", "Browse market", lambda e: None),
    ])


def _login_preview_user(mock: bool) -> None:
    """Log in a demo user so route guards let the preview through."""
    if mock:
        session.login(dict(md.MOCK_USER))
        return
    from Databases.Database_Setup import setup_database
    from Databases.User_Queries import get_user_by_username

    setup_database()
    user = get_user_by_username("amina_w")
    if user:
        session.login(user)


def main() -> None:
    """Parse arguments and launch Flet."""
    parser = argparse.ArgumentParser(description="Preview one AgriLink page.")
    parser.add_argument("page", nargs="?", default="components",
                        help="components, login, register, home, market, crop/1, listing/1, sell, "
                             "messages, messages/2, chatbot, profile/1, settings")
    parser.add_argument("--mock", action="store_true", help="use UI/mock_data instead of the database")
    parser.add_argument("--dark", action="store_true", help="start in dark mode")
    parser.add_argument("--scale", type=float, default=1.0, help="text scale, e.g. 1.3")
    parser.add_argument("--web", action="store_true", help="open in a web browser")
    args = parser.parse_args()

    md.set_mock(args.mock or args.page == "components")
    target_route = "/" + args.page.strip("/")

    def app(page: ft.Page) -> None:
        if args.page != "login" and args.page != "register":
            _login_preview_user(md.USE_MOCK)
            if session.user:
                session.user.update({"dark_mode": int(args.dark), "text_scale": args.scale})
        apply_theme(page, dark=args.dark, text_scale=args.scale)
        page.title = f"Preview: {args.page}"
        try:
            page.window.width, page.window.height = 430, 860
        except AttributeError:
            pass

        if args.page == "components":
            page.views.clear()
            page.views.append(build_components_gallery(page))
            page.on_route_change = lambda e: None
            page.update()
            return

        import main as app_main

        page.route = target_route
        app_main.main(page)

    view = ft.AppView.WEB_BROWSER if args.web else ft.AppView.FLET_APP
    ft.app(target=app, view=view, assets_dir=config.ASSETS_DIR)


if __name__ == "__main__":
    main()
