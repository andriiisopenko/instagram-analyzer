# Instagram Non-Followers Analyzer

A small Python CLI application that finds accounts a target Instagram profile follows but that do not follow it back. It uses [Instaloader](https://instaloader.github.io/) and does not use the official Instagram API.

## MVP features

- Accepts a profile URL, `@username`, or plain username.
- Authenticates through a visible browser launched by Playwright.
- Supports installed Chrome, Chromium, Firefox, Brave, and Edge browsers on macOS.
- Lets the user complete passwords, 2FA, checkpoints, and confirmations in Instagram itself.
- Saves multiple Instagram accounts with one private Playwright session per account.
- Selects, adds, refreshes, and deletes saved accounts from the CLI.
- Collects following and follower usernames with progress bars.
- Calculates non-followers with set comparison.
- Marks accounts seen in earlier runs for the same target with `[checked]`.
- Prints an annotated result and saves a timestamped run-history TXT report.
- Reports expected login, access, network, and rate-limit failures cleanly.

## Requirements

- Python 3.11 or newer
- An Instagram account that can access the target profile
- Network access to Instagram

## Installation

Clone the repository and enter its directory. A virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Usage

Run the interactive CLI:

```bash
python main.py
```

Select or add an authenticated Instagram account first. Then analyze that account's own profile or enter another profile as an Instagram URL, `@username`, or username.

## Authentication

Authentication uses this flow:

1. Saved accounts are loaded from the local SQLite database.
2. The user can select, add, or delete an account.
3. A selected account's Playwright session is validated and reused when possible.
4. New or expired sessions use the visible manual browser-login flow.
5. The user chooses the authenticated account's own profile or enters another target.

The terminal never asks for or stores an Instagram password or 2FA code. The application does not autofill credentials, read cookies from an existing browser profile, or bypass Instagram security checks.

### Manual browser authentication on macOS

1. Run `python main.py`.
2. Choose one of the detected browsers.
3. Log in manually in the browser window opened by the application.
4. Complete any 2FA, checkpoint, or device confirmation requested by Instagram.
5. Keep the browser open until the application confirms authentication.

The application uses Playwright and supports Google Chrome, Chromium, Firefox, Brave Browser, and Microsoft Edge when detected. If none is installed, Playwright-managed Chromium can be installed with `python -m playwright install chromium`. Safari is not offered because Playwright cannot reliably launch the installed Safari application. No Full Disk Access or browser cookie database access is required.

Account metadata is stored in `data/accounts.db`. Each account has a separate private Playwright state in `data/sessions/<username>.json`. The database contains only the username, session filename, and timestamps; it never contains passwords, cookies, or raw storage state. Expired sessions keep their account record and can be replaced through the same manual browser-login flow. The previous `sessions/instagram_storage_state.json` is migrated automatically when it is valid and no accounts have been saved yet.

Deleting an account removes only its database record and session file. Analysis history is preserved. The database and session directory are ignored by Git. Session state is sensitive and must never be shared or committed.

## Checked account history

The separate `data/history.db` database accumulates non-follower history independently for each target profile. An account that appeared in any earlier completed run for the same target is marked `[checked]`; its first appearance has no marker. The database stores usernames, first/last seen timestamps, and the number of appearances. It does not store passwords, cookies, or Playwright state.

Example:

```text
========================================
Instagram Non-Followers Analyzer
========================================

Saved Instagram accounts:

1. @my_account

A. Add another account
D. Delete saved account
0. Exit

> 1

Using @my_account

Checking saved session...
Session is valid.

Logged in as: @my_account

Profile to analyze:

1. @my_account
2. Enter another profile
0. Back

> 2

Enter a profile URL, @username, or username.
Example: https://instagram.com/example or @example

Target profile:
> https://instagram.com/example

Target: @example

Loading @example...

Collecting following...
Following: 100%|████████████████| 623/623

Collecting followers...
Followers: 100%|████████████████| 581/581

Analyzing...

Following: 623
Followers: 581
Non-followers: 73

user1  [checked]
user2
user3  [checked]

Saved to:
output/history/2026-08-17_14-37-22.txt
```

Every completed run creates a new report in `output/history/`. The filename uses the local run start time, and collision suffixes prevent overwriting earlier reports. Reports include the target, start time, statistics, and the complete numbered non-followers list.

Example report:

```text
Instagram Non-Followers Analyzer

Run started: 2026-08-17 14:37:22
Authenticated as: @my_account
Target: @example

Following: 623
Followers: 581
Non-followers: 73

Non-followers:

user1  [checked]
user2
user3  [checked]

Total: 3
Previously checked: 2
New: 1
```

The `output/` directory is also ignored by Git.

## Project structure

```text
instagram-analyzer/
├── main.py
├── instagram_analyzer/
│   ├── __init__.py
│   ├── accounts.py
│   ├── analyzer.py
│   ├── auth.py
│   ├── browser_auth.py
│   ├── history.py
│   ├── output.py
│   ├── profile.py
│   ├── rate_limit.py
│   └── utils.py
├── tests/
├── data/                  # Local database and private sessions (Git-ignored)
├── requirements.txt
├── .gitignore
├── README.md
└── LICENSE
```

## Rate limits and account safety

The application retains Instaloader's built-in rate limiting and adds only a small delay between the two main collection operations. It does not bypass Instagram restrictions or retry aggressively.

Instagram may restrict automated requests. This application cannot guarantee that an account will never encounter temporary rate limiting. Use it conservatively, avoid repeated scans in a short period, and stop if Instagram asks you to verify account activity.

## Tests

The unit tests do not access Instagram or require credentials:

```bash
python -m pytest
```

## Future functionality

- Followers the target does not follow back
- Mutual followers
- Comparison with previous scans
- Unfollower and new-follower detection
- CSV and JSON export
- Statistics and summaries
- Multiple target profiles
