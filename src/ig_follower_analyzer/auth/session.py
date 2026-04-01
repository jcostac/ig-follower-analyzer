from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from ..models import Credentials
from ..selectors import InstagramSelectors

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - optional at import time
    dotenv_values = None

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional at import time
    sync_playwright = None

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright
else:  # pragma: no cover - runtime fallback typing
    Browser = Any
    BrowserContext = Any
    Page = Any
    Playwright = Any

LOGIN_URL = "https://www.instagram.com/?flo=true"
LOGOUT_URL = "https://www.instagram.com/accounts/logout/"

T = TypeVar("T")


class LoginChallengeError(RuntimeError):
    """Raised when login requires 2FA/challenge resolution."""


class LoginFailedError(RuntimeError):
    """Raised when login could not be completed."""


@dataclass(frozen=True)
class LoginAttemptContext:
    headless: bool
    allow_manual_challenge: bool


def resolve_credentials(
    *,
    cli_username: str | None,
    cli_password: str | None,
    cli_email: str | None,
    env_path: Path,
    prompt_for_missing: bool = True,
) -> Credentials:
    env_values = _load_env_values(env_path)

    username = cli_username or env_values.get("IG_USERNAME")
    password = cli_password or env_values.get("IG_PASSWORD")
    email = cli_email or env_values.get("IG_EMAIL")

    if prompt_for_missing:
        if not username:
            username = input("Instagram username: ").strip()
        if not password:
            password = getpass("Instagram password: ").strip()

    if not username:
        raise ValueError("missing Instagram username; pass --username or define IG_USERNAME in .env")
    if not password:
        raise ValueError("missing Instagram password; pass --password or define IG_PASSWORD in .env")

    return Credentials(username=username, password=password, email=email)


def login_with_headful_fallback(
    attempt_login: Callable[[LoginAttemptContext], T],
    *,
    force_headful: bool,
) -> T:
    if force_headful:
        return attempt_login(LoginAttemptContext(headless=False, allow_manual_challenge=True))

    try:
        return attempt_login(LoginAttemptContext(headless=True, allow_manual_challenge=False))
    except LoginChallengeError:
        return attempt_login(LoginAttemptContext(headless=False, allow_manual_challenge=True))


def run_with_logout(work: Callable[[], T], logout: Callable[[], None]) -> T:
    try:
        return work()
    finally:
        logout()


class InstagramBrowserSession:
    def __init__(
        self,
        *,
        selectors: InstagramSelectors,
        headless: bool,
        state_file: Path,
        fresh_login: bool,
    ) -> None:
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Install dependencies and run `playwright install chromium`."
            )

        self._selectors = selectors
        self._state_file = state_file
        self._playwright: Playwright = sync_playwright().start()
        self._browser: Browser = self._playwright.chromium.launch(headless=headless)

        context_kwargs: dict[str, object] = {}
        if not fresh_login and state_file.exists():
            context_kwargs["storage_state"] = str(state_file)

        self._context: BrowserContext = self._browser.new_context(**context_kwargs)
        self.page: Page = self._context.new_page()

    def login(self, credentials: Credentials, *, allow_manual_challenge: bool) -> None:
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        self._accept_cookie_dialog_if_present()

        if self._is_authenticated(credentials.username):
            return

        self._fill_login_form(credentials)
        self.page.locator(self._selectors.login_button).first.click()
        self.page.wait_for_timeout(3500)

        if self._is_challenge_page():
            if allow_manual_challenge:
                self._wait_for_manual_challenge_completion(credentials.username)
            else:
                raise LoginChallengeError("Instagram requested 2FA/challenge in headless mode")

        self._dismiss_post_login_prompts()

        if not self._is_authenticated(credentials.username):
            if allow_manual_challenge:
                self._wait_for_manual_challenge_completion(credentials.username)
            if not self._is_authenticated(credentials.username):
                raise LoginFailedError("Instagram login did not complete successfully")

    def persist_storage_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(self._state_file))

    def logout(self) -> None:
        try:
            self.page.goto(LOGOUT_URL, wait_until="domcontentloaded")
            self.page.wait_for_timeout(1500)
        except Exception:
            return

    def close(self) -> None:
        close_errors: list[Exception] = []
        for closer in (self._context.close, self._browser.close, self._playwright.stop):
            try:
                closer()
            except Exception as err:  # pragma: no cover - best effort cleanup
                close_errors.append(err)
        if close_errors:
            raise RuntimeError(f"failed to close browser resources cleanly: {close_errors[0]}")

    def _fill_login_form(self, credentials: Credentials) -> None:
        username_field = self.page.locator(self._selectors.username_input).first
        password_field = self.page.locator(self._selectors.password_input).first

        if username_field.count() == 0 or password_field.count() == 0:
            raise LoginFailedError("Instagram login form was not found")

        identifier = credentials.username or credentials.email or ""
        username_field.fill(identifier)
        password_field.fill(credentials.password)

    def _is_authenticated(self, username: str) -> bool:
        self.page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
        self.page.wait_for_timeout(1200)
        url = self.page.url.lower()
        return "accounts/login" not in url and "challenge" not in url and "checkpoint" not in url

    def _is_challenge_page(self) -> bool:
        url = self.page.url.lower()
        if any(marker in url for marker in ("challenge", "checkpoint", "two_factor")):
            return True
        page_text = self.page.content().lower()
        return any(
            marker in page_text
            for marker in (
                "enter security code",
                "choose a way to confirm",
                "two-factor",
                "suspicious login",
                "checkpoint",
            )
        )

    def _wait_for_manual_challenge_completion(self, username: str) -> None:
        print(
            "Instagram challenge detected. Complete 2FA/challenge in the open browser, "
            "then press ENTER here."
        )
        input("Press ENTER after login is complete: ")
        if not self._is_authenticated(username):
            raise LoginFailedError("manual login flow did not finish authentication")

    def _dismiss_post_login_prompts(self) -> None:
        for label in ("Not now", "Not Now", "Cancel"):
            locator = self.page.get_by_role("button", name=label)
            if locator.count() > 0:
                locator.first.click()
                self.page.wait_for_timeout(700)

    def _accept_cookie_dialog_if_present(self) -> None:
        for label in ("Allow all cookies", "Only allow essential cookies", "Accept all"):
            locator = self.page.get_by_role("button", name=label)
            if locator.count() > 0:
                locator.first.click()
                self.page.wait_for_timeout(500)
                break


def _load_env_values(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    if dotenv_values is not None:
        parsed = dotenv_values(env_path)
        return {key: value for key, value in parsed.items() if value is not None}

    pairs: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
            continue
        key, value = cleaned.split("=", 1)
        pairs[key.strip()] = value.strip()
    return pairs
