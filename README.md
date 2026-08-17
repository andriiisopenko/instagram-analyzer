# Instagram Non-Followers Analyzer

A small Python CLI application that finds accounts a target Instagram profile follows but that do not follow it back. It uses [Instaloader](https://instaloader.github.io/) and does not use the official Instagram API.

## MVP features

- Accepts a profile URL, `@username`, or plain username.
- Authenticates through a visible browser launched by Playwright.
- Supports installed Chrome, Chromium, Firefox, Brave, and Edge browsers on macOS.
- Lets the user complete passwords, 2FA, checkpoints, and confirmations in Instagram itself.
- Reuses a local Playwright authentication state after validating it.
- Collects following and follower usernames with progress bars.
- Calculates non-followers with set comparison.
- Prints a numbered result and saves a timestamped run-history TXT report.
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

Enter the target profile as an Instagram URL, `@username`, or username.

## Authentication

Authentication uses this flow:

1. A saved Playwright Instagram session is validated and reused when possible.
2. If no valid session exists, the application detects supported browsers installed on the Mac.
3. The selected browser opens Instagram in a visible Playwright-controlled window.
4. The user completes the entire login manually in Instagram.
5. The authenticated browser state is saved and transferred to Instaloader for the existing analysis.

The terminal never asks for or stores an Instagram password or 2FA code. The application does not autofill credentials, read cookies from an existing browser profile, or bypass Instagram security checks.

### Manual browser authentication on macOS

1. Run `python main.py`.
2. Choose one of the detected browsers.
3. Log in manually in the browser window opened by the application.
4. Complete any 2FA, checkpoint, or device confirmation requested by Instagram.
5. Keep the browser open until the application confirms authentication.

The application uses Playwright and supports Google Chrome, Chromium, Firefox, Brave Browser, and Microsoft Edge when detected. If none is installed, Playwright-managed Chromium can be installed with `python -m playwright install chromium`. Safari is not offered because Playwright cannot reliably launch the installed Safari application. No Full Disk Access or browser cookie database access is required.

After successful login, Playwright saves the browser authentication state to `sessions/instagram_storage_state.json` with restricted permissions. Future launches create an isolated Playwright context from that state, validate it with Instagram, and continue without another login when it remains valid. Expired state is removed and replaced after a new manual login. The `sessions/` directory is ignored by Git.

The saved state contains sensitive browser authentication data. Never share or commit it.

Example:

```text
========================================
Instagram Non-Followers Analyzer
========================================

Target profile:
> https://instagram.com/example

Target: @example

Checking saved session...
No valid saved session found.

Choose browser:

1. Google Chrome
2. Firefox
3. Brave Browser
0. Cancel

> 1

Browser opened.

Log in to Instagram manually in the browser.
Complete any 2FA, security check, checkpoint, or confirmation requested by Instagram.

Waiting for successful Instagram login...
Instagram login successful.
Saving session...
Session saved.
Authenticated as @my_account.

Loading @example...

Collecting following...
Following: 100%|████████████████| 623/623

Collecting followers...
Followers: 100%|████████████████| 581/581

Analyzing...

Following: 623
Followers: 581
Non-followers: 73

1. @user1
2. @user2
3. @user3

Saved to:
output/history/2026-08-17_14-37-22.txt
```

Every completed run creates a new report in `output/history/`. The filename uses the local run start time, and collision suffixes prevent overwriting earlier reports. Reports include the target, start time, statistics, and the complete numbered non-followers list.

Example report:

```text
Instagram Non-Followers Analyzer

Run started: 2026-08-17 14:37:22
Target: @example

Following: 623
Followers: 581
Non-followers: 73

Non-followers:

1. @user1
2. @user2
3. @user3
```

The `output/` directory is also ignored by Git.

## Project structure

```text
instagram-analyzer/
├── main.py
├── instagram_analyzer/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── auth.py
│   ├── browser_auth.py
│   ├── output.py
│   ├── profile.py
│   ├── rate_limit.py
│   └── utils.py
├── tests/
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
