# Instagram Non-Followers Analyzer

A small Python CLI application that finds accounts a target Instagram profile follows but that do not follow it back. It uses [Instaloader](https://instaloader.github.io/) and does not use the official Instagram API.

## MVP features

- Accepts a profile URL, `@username`, or plain username.
- Authenticates with an Instagram username and a hidden password prompt.
- Supports Instagram two-factor authentication.
- Reuses local Instaloader session files after validating them.
- Collects following and follower usernames with progress bars.
- Calculates non-followers with set comparison.
- Prints a numbered result and saves an unnumbered TXT file.
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

Enter the target profile as an Instagram URL, `@username`, or username. Then enter the username of the Instagram account used for authentication. Password input is hidden.

If Instagram requires two-factor authentication, the application asks for the current 2FA code. Passwords and 2FA codes are never written to disk. After a successful login, the Instaloader session cookie is stored in `sessions/session-<username>` with restricted file permissions. The `sessions/` directory is ignored by Git.

Example:

```text
========================================
Instagram Non-Followers Analyzer
========================================

Target profile:
> https://instagram.com/example

Target: @example

Instagram login: my_account
Password:

Logging in...
Login successful.

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
output/non_followers_example.txt
```

Generated files contain one username per line without numbering:

```text
@user1
@user2
@user3
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
