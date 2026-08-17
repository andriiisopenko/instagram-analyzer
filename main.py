"""CLI entry point for the Instagram non-followers analyzer."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime

import instaloader

from instagram_analyzer.accounts import AccountStore
from instagram_analyzer.analyzer import find_non_followers
from instagram_analyzer.auth import AuthenticatedAccount, select_authenticated_account
from instagram_analyzer.browser_auth import BrowserAuthenticationError
from instagram_analyzer.output import (
    print_numbered_usernames,
    print_summary,
    save_history_report,
)
from instagram_analyzer.profile import (
    collect_followers,
    collect_following,
    resolve_profile,
)
from instagram_analyzer.rate_limit import pause_between_operations
from instagram_analyzer.utils import normalize_username


def run() -> int:
    """Run the interactive CLI and return a process exit code."""
    print("=" * 40)
    print("Instagram Non-Followers Analyzer")
    print("=" * 40)
    print()

    try:
        account_store = AccountStore()
        while True:
            authenticated = select_authenticated_account(account_store)
            if authenticated is None:
                print("Authentication cancelled.")
                return 0

            target_username = _choose_target_profile(authenticated.username)
            if target_username is None:
                print()
                continue

            run_started_at = datetime.now()
            return _run_analysis(authenticated, target_username, run_started_at)
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.", file=sys.stderr)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
    except BrowserAuthenticationError as error:
        print(f"Error: {error}", file=sys.stderr)
    except sqlite3.Error as error:
        print(f"Error: Local account database failure: {error}", file=sys.stderr)
    except instaloader.ProfileNotExistsException:
        print("Error: Instagram profile not found.", file=sys.stderr)
    except instaloader.PrivateProfileNotFollowedException:
        print(
            "Error: This private profile is not accessible to the authenticated account.",
            file=sys.stderr,
        )
    except instaloader.LoginRequiredException:
        print("Error: Instagram login is required for this operation.", file=sys.stderr)
    except instaloader.TooManyRequestsException:
        print(
            "Error: Instagram rate limit reached. Wait before trying again.",
            file=sys.stderr,
        )
    except instaloader.ConnectionException as error:
        print(f"Error: Network or Instagram connection failure: {error}", file=sys.stderr)
    except instaloader.BadResponseException as error:
        print(f"Error: Unexpected response from Instagram: {error}", file=sys.stderr)
    except instaloader.LoginException as error:
        print(f"Error: Instagram login failed: {error}", file=sys.stderr)
    except instaloader.InstaloaderException as error:
        print(f"Error: Instagram request failed: {error}", file=sys.stderr)

    return 1


def _choose_target_profile(authenticated_username: str) -> str | None:
    print(f"\nLogged in as: @{authenticated_username}")
    print("\nProfile to analyze:\n")
    print(f"1. @{authenticated_username}")
    print("2. Enter another profile")
    print("0. Back")

    while True:
        choice = input("\n> ").strip()
        if choice == "0":
            return None
        if choice == "1":
            return authenticated_username
        if choice == "2":
            print("\nEnter a profile URL, @username, or username.")
            print("Example: https://instagram.com/example or @example")
            return normalize_username(input("\nTarget profile:\n> "))
        print("Invalid choice. Enter 0, 1, or 2.")


def _run_analysis(
    authenticated: AuthenticatedAccount,
    target_username: str,
    run_started_at: datetime,
) -> int:
    print(f"\nTarget: @{target_username}")
    print(f"\nLoading @{target_username}...")
    target_profile = resolve_profile(authenticated.loader, target_username)

    print("\nCollecting following...")
    following = collect_following(target_profile)
    pause_between_operations()

    print("\nCollecting followers...")
    followers = collect_followers(target_profile)

    print("\nAnalyzing...")
    non_followers = sorted(find_non_followers(following, followers))

    print()
    print_summary(len(following), len(followers), len(non_followers))
    if non_followers:
        print()
        print_numbered_usernames(non_followers)
    else:
        print("\nEveryone you follow follows you back.")

    output_path = save_history_report(
        non_followers,
        authenticated.username,
        target_username,
        len(following),
        len(followers),
        run_started_at,
    )
    print(f"\nSaved to:\n{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
