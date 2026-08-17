"""CLI entry point for the Instagram non-followers analyzer."""

from __future__ import annotations

import sys

import instaloader

from instagram_analyzer.analyzer import find_non_followers
from instagram_analyzer.auth import authenticate
from instagram_analyzer.output import (
    print_numbered_usernames,
    print_summary,
    save_usernames,
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

    print("Enter a profile URL, @username, or username.")
    print("Example: https://instagram.com/example or @example")
    print()
    try:
        target_username = normalize_username(input("Target profile:\n> "))
        print(f"\nTarget: @{target_username}\n")

        login_username = normalize_username(input("Instagram login: "))
        print()
        loader = authenticate(login_username)

        print(f"\nLoading @{target_username}...")
        target_profile = resolve_profile(loader, target_username)

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

        output_path = save_usernames(non_followers, target_username)
        print(f"\nSaved to:\n{output_path}")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.", file=sys.stderr)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
    except instaloader.BadCredentialsException:
        print("Error: Incorrect password or invalid 2FA code.", file=sys.stderr)
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


if __name__ == "__main__":
    raise SystemExit(run())
