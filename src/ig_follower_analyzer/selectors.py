from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstagramSelectors:
    username_input: str = "input[name='username']"
    password_input: str = "input[name='password']"
    login_button: str = "button[type='submit']"
    dialog: str = "div[role='dialog']"
    dialog_links: str = "div[role='dialog'] a[href^='/']"
    dialog_scroll_container: str = "div[role='dialog'] div.x1rife3k"
    following_button_xpath: str = "//a[contains(@href, '/following/')]|//span[text()='following']/ancestor::a"
    followers_button_xpath: str = "//a[contains(@href, '/followers/')]|//span[text()='followers']/ancestor::a"
    following_action_button: str = "button:has-text('Following'), button:has-text('Requested')"
    unfollow_confirm_button: str = "button:has-text('Unfollow')"
