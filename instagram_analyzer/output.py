"""Console and file output helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from html import escape
from pathlib import Path

from instagram_analyzer.history import CheckedAccount


def print_summary(following_count: int, follower_count: int, result_count: int) -> None:
    """Print relationship totals."""
    print(f"Following: {following_count}")
    print(f"Followers: {follower_count}")
    print(f"Non-followers: {result_count}")


def print_numbered_usernames(usernames: Iterable[str]) -> None:
    """Print usernames as a numbered list."""
    for index, username in enumerate(usernames, start=1):
        print(f"{index}. @{username}")


def print_checked_accounts(accounts: Iterable[CheckedAccount]) -> None:
    """Print non-followers with cumulative history annotations."""
    for line in format_checked_accounts(accounts):
        print(line)


def save_usernames(
    usernames: Iterable[str],
    target_username: str,
    *,
    output_directory: Path = Path("output"),
) -> Path:
    """Save one @username per line and return the output path."""
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"non_followers_{target_username}.txt"
    contents = "".join(f"@{username}\n" for username in usernames)
    output_path.write_text(contents, encoding="utf-8")
    return output_path


def save_history_report(
    accounts: Iterable[CheckedAccount],
    authenticated_username: str,
    target_username: str,
    following_count: int,
    follower_count: int,
    run_started_at: datetime,
    *,
    history_directory: Path = Path("output/history"),
) -> Path:
    """Save a timestamped analysis report without overwriting earlier runs."""
    history_directory.mkdir(parents=True, exist_ok=True)
    output_path = _available_history_path(history_directory, run_started_at)
    account_list = list(accounts)
    previously_checked_count = sum(
        account.previously_checked for account in account_list
    )

    lines = [
        "Instagram Non-Followers Analyzer",
        "",
        f"Run started: {run_started_at:%Y-%m-%d %H:%M:%S}",
        f"Authenticated as: @{authenticated_username}",
        f"Target: @{target_username}",
        "",
        f"Following: {following_count}",
        f"Followers: {follower_count}",
        f"Non-followers: {len(account_list)}",
        "",
        "Non-followers:",
        "",
    ]
    if account_list:
        lines.extend(format_checked_accounts(account_list))
    else:
        lines.append("None")
    lines.extend(
        [
            "",
            f"Total: {len(account_list)}",
            f"Previously checked: {previously_checked_count}",
            f"New: {len(account_list) - previously_checked_count}",
        ]
    )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def save_html_report(
    accounts: Iterable[CheckedAccount],
    authenticated_username: str,
    target_username: str,
    following_count: int,
    follower_count: int,
    run_started_at: datetime,
    *,
    html_directory: Path = Path("reports/html"),
) -> Path:
    """Save a standalone timestamped HTML report with embedded styling."""
    html_directory.mkdir(parents=True, exist_ok=True)
    output_path = _available_timestamp_path(html_directory, run_started_at, ".html")
    account_list = list(accounts)
    checked_accounts = [account for account in account_list if account.previously_checked]
    new_accounts = [account for account in account_list if not account.previously_checked]

    def account_rows(items: list[CheckedAccount]) -> str:
        if not items:
            return '<li class="empty">None</li>'
        return "\n".join(
            '<li><span class="username">@{}</span>{}</li>'.format(
                escape(account.username),
                '<span class="checked">[checked]</span>'
                if account.previously_checked
                else "",
            )
            for account in items
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Instagram analysis · @{escape(target_username)}</title>
  <style>
    :root {{ color-scheme: light; --ink: #161616; --paper: #ffffff; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: min(1040px, calc(100% - 40px)); margin: 0 auto; padding: 72px 0 96px; }}
    header {{ display: flex; justify-content: space-between; gap: 32px; align-items: end; padding-bottom: 32px; border-bottom: 2px solid var(--ink); }}
    .eyebrow {{ margin: 0 0 10px; font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
    h1 {{ margin: 0; max-width: 720px; font-size: clamp(38px, 7vw, 72px); line-height: .98; letter-spacing: -.055em; }}
    .meta {{ margin: 0; text-align: right; white-space: nowrap; }}
    .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); margin: 32px 0 64px; border: 1px solid var(--ink); }}
    .stat {{ min-width: 0; padding: 22px; border-right: 1px solid var(--ink); }}
    .stat:last-child {{ border-right: 0; }}
    .value {{ display: block; font-size: 32px; font-weight: 700; letter-spacing: -.04em; }}
    .label {{ display: block; margin-top: 4px; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .lists {{ display: grid; grid-template-columns: 1fr 1fr; gap: 56px; }}
    section:first-child {{ grid-column: 1 / -1; }}
    h2 {{ margin: 0 0 16px; font-size: 22px; letter-spacing: -.02em; }}
    ol, ul {{ list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--ink); }}
    li {{ display: flex; justify-content: space-between; gap: 20px; padding: 11px 0; border-bottom: 1px solid var(--ink); }}
    .checked {{ font-size: 12px; font-weight: 700; letter-spacing: .06em; }}
    .empty {{ margin: 0; padding: 16px 0; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink); }}
    footer {{ margin-top: 72px; padding-top: 20px; border-top: 1px solid var(--ink); font-size: 12px; }}
    @media (max-width: 780px) {{
      main {{ width: min(100% - 28px, 1040px); padding-top: 40px; }}
      header {{ align-items: start; flex-direction: column; }}
      .meta {{ text-align: left; }}
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .stat {{ border-bottom: 1px solid var(--ink); }}
      .stat:nth-child(2n) {{ border-right: 0; }}
      .stat:last-child {{ grid-column: 1 / -1; border-bottom: 0; }}
      .lists {{ grid-template-columns: 1fr; gap: 40px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <p class="eyebrow">Instagram analysis</p>
        <h1>@{escape(target_username)}</h1>
      </div>
      <p class="meta">{run_started_at:%Y-%m-%d %H:%M:%S}<br>Authenticated as @{escape(authenticated_username)}</p>
    </header>
    <div class="stats" aria-label="Analysis statistics">
      <div class="stat"><span class="value">{following_count}</span><span class="label">Following</span></div>
      <div class="stat"><span class="value">{follower_count}</span><span class="label">Followers</span></div>
      <div class="stat"><span class="value">{len(account_list)}</span><span class="label">Total analyzed</span></div>
      <div class="stat"><span class="value">{len(checked_accounts)}</span><span class="label">Previously checked</span></div>
      <div class="stat"><span class="value">{len(new_accounts)}</span><span class="label">New</span></div>
    </div>
    <div class="lists">
      <section>
        <h2>Non-followers</h2>
        <ol>{account_rows(account_list)}</ol>
      </section>
      <section>
        <h2>New</h2>
        <ul>{account_rows(new_accounts)}</ul>
      </section>
      <section>
        <h2>Previously checked</h2>
        <ul>{account_rows(checked_accounts)}</ul>
      </section>
    </div>
    <footer>Standalone report · all styles are embedded in this file.</footer>
  </main>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path


def format_checked_accounts(accounts: Iterable[CheckedAccount]) -> list[str]:
    """Format account rows identically for console and text reports."""
    account_list = list(accounts)
    if not account_list:
        return []
    username_width = max(len(account.username) for account in account_list)
    return [
        (
            f"{account.username:<{username_width}}  [checked]"
            if account.previously_checked
            else account.username
        )
        for account in account_list
    ]


def _available_history_path(
    history_directory: Path,
    run_started_at: datetime,
) -> Path:
    return _available_timestamp_path(history_directory, run_started_at, ".txt")


def _available_timestamp_path(
    directory: Path,
    run_started_at: datetime,
    suffix: str,
) -> Path:
    timestamp = run_started_at.strftime("%Y-%m-%d_%H-%M-%S")
    output_path = directory / f"{timestamp}{suffix}"
    collision_index = 2
    while output_path.exists():
        output_path = directory / f"{timestamp}_{collision_index}{suffix}"
        collision_index += 1
    return output_path
