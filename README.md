# ig-follower-analyzer

CLI tool to analyze your Instagram relationships and optionally unfollow accounts that do not follow you back.

## Features

- Logs into Instagram at `https://www.instagram.com/?flo=true`
- Uses credentials from CLI args or `.env` (`CLI > .env > prompt`)
- Auto-fallback from headless to headful browser when login challenge/2FA appears
- Scrapes your full `following` and `followers` lists
- Computes:
  - `following`
  - `followers`
  - `follow_you_back` (`following ∩ followers`)
  - `you_dont_follow_back` (`followers - following`)
  - `dont_follow_you_back` (`following - followers`)
- Shows indexed `dont_follow_you_back` list and supports selection syntax (`1,3,8-12` or `all`)
- Requires explicit `UNFOLLOW` confirmation token before destructive actions
- Writes JSON and/or CSV reports, including unfollow action logs
- Always attempts logout before closing browser

## Setup

1. Create and activate a virtualenv.
2. Install dependencies:

```bash
pip install -e .[dev]
playwright install chromium
```

3. Copy env template and fill credentials:

```bash
cp .env.template .env
```

## Usage

Basic analysis + optional unfollow:

```bash
PYTHONPATH=src python -m ig_follower_analyzer
```

Equivalent installed script:

```bash
ig-follower-analyzer
```

Useful options:

```bash
ig-follower-analyzer --headful
ig-follower-analyzer --no-unfollow
ig-follower-analyzer --select "1,3,8-12"
ig-follower-analyzer --fresh-login
ig-follower-analyzer --format json,csv --output-dir reports
```

## Notes

- Instagram UI selectors can change over time. Selector constants are centralized in `src/ig_follower_analyzer/selectors.py`.
- If challenge/2FA appears, complete it in the opened browser window and return to terminal when prompted.
