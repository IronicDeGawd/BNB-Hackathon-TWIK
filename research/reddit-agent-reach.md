# Reddit Social Signal: Agent Reach + Fallback Reference

---

## Overview

**Agent Reach** (`github.com/Panniantong/Agent-Reach`) is a real, maintained open-source
Python CLI tool. It acts as a routing/multiplexer layer: it discovers, installs, and manages
backend CLIs for 13+ web platforms (Twitter, Reddit, YouTube, GitHub, etc.) and auto-switches
to the next backend when one path fails. It is maintained primarily by a single developer
(Panniantong), with some community forks.

The **Reddit backend** for Agent Reach is **`rdt-cli`** — a separate CLI maintained under the
`public-clis` org. It uses cookie-based authentication (extracted from your logged-in browser)
rather than official Reddit OAuth. This means zero API cost and no approval queue, but it
requires a logged-in browser session and is subject to Reddit's anti-bot detection.

**`agent-reach doctor`** is a real health-check command that prints the status of every
configured platform channel (ready / needs config / error) and shows which backend is active.

---

## Agent Reach (Primary)

### Install

```bash
# Option 1: pip direct from GitHub
pip install https://github.com/Panniantong/agent-reach/archive/main.zip
agent-reach install --env=auto

# Option 2: as a skills package (for Claude Code / Cursor / Windsurf)
npx skills add Panniantong/Agent-Reach@agent-reach

# Install rdt-cli (the Reddit backend) separately
pipx install 'git+https://github.com/public-clis/rdt-cli.git'
# or
uv tool install rdt-cli
```

### Auth (throwaway Reddit account)

Reddit blocks all anonymous access (403). A logged-in session is required.
Using a throwaway is strongly recommended — anti-bot systems can flag and suspend accounts.

```bash
# Step 1: Log in to reddit.com in any browser (Chrome, Firefox, Edge, Brave)
#         using your throwaway account

# Step 2: Run rdt login — it auto-extracts cookies from your browser
rdt login
# Credentials saved to: ~/.config/rdt-cli/credential.json
# Session valid for ~7 days; re-run rdt login to refresh
```

> Note: rdt-cli uses cookie extraction, NOT Reddit's OAuth API. This bypasses the official API
> approval process entirely, at the cost of session expiry and potential TOS risk.

### Query a subreddit

```bash
# Search a specific subreddit
rdt search "BNB token" -r CryptoCurrency -s top -t week

# Search across all of Reddit
rdt search "BNBChain launch" -s new

# Search flags:
#   -r / --subreddit   : scope to one subreddit
#   -s / --sort        : top | new | hot | relevance
#   -t / --time        : hour | day | week | month | year | all
#   -o FILE            : export results to CSV or JSON
#   --json             : output as JSON
#   --compact          : condensed output

# Read a post with all comments
rdt read POST_ID
rdt read POST_ID --expand-more   # load collapsed/hidden comments

# Read Nth result from the last listing
rdt show 3 --expand-more
```

**Multi-sub pattern for the trading agent:**

```bash
for SUB in CryptoCurrency BNBChainOfficial; do
  rdt search "$TOKEN_SYMBOL" -r "$SUB" -s new -t day --json >> /tmp/reddit_signals.json
done
```

### `agent-reach doctor` health check

```bash
agent-reach doctor
```

Sample output (condensed):

```
✅ github      — gh CLI (zero config)
✅ youtube     — yt-dlp (zero config)
✅ web         — Jina Reader (zero config)
✅ rss         — feedparser (zero config)
🔧 reddit      — rdt-cli ✅ Authenticated as your-throwaway
🔧 twitter     — twitter-cli (needs cookie)
🔍 web-search  — Exa (needs free API key)
```

If reddit shows `❌ Not configured`, run `rdt login` and re-check.

The doctor command also tells you **which backend is active** for each platform,
which is useful when rdt-cli falls back or breaks.

---

## Reddit Official API Fallback

Use this path if Agent Reach / rdt-cli becomes unreliable (VPS IP bans, cookie expiry,
single-maintainer abandonment risk) or if you need higher reliability for production.

### OAuth App Setup

1. Go to `https://www.reddit.com/prefs/apps`
2. Click "Create app" → choose **script** (for personal/bot use)
3. Fill in name, description, redirect URI = `http://localhost:8080`
4. After creation, copy:
   - **Client ID**: shown below the app name (the short alphanumeric string)
   - **Client Secret**: click "edit" to reveal
5. As of 2025, Reddit requires you to agree to the **Responsible Builder Policy** and
   submit a usage description. Personal/low-volume projects are typically approved in
   days; commercial use takes weeks.

### /search.json endpoint (params, examples)

Base URL pattern:

```
https://oauth.reddit.com/r/{subreddit}/search.json
```

Or cross-subreddit:

```
https://oauth.reddit.com/search.json
```

Key query parameters:

| Param       | Description                                         | Example          |
|-------------|-----------------------------------------------------|------------------|
| `q`         | Search query string                                 | `BNB token`      |
| `restrict_sr` | `true` = search only this subreddit (when in /r/) | `true`           |
| `sort`      | `relevance` \| `hot` \| `top` \| `new` \| `comments` | `new`          |
| `t`         | Time filter: `hour` \| `day` \| `week` \| `month` \| `year` \| `all` | `week` |
| `limit`     | Results per page (max 100)                          | `25`             |
| `after`     | Pagination cursor (fullname of last post)           | `t3_abc123`      |
| `type`      | `link` (posts) \| `comment` (not always available) | `link`           |

Example authenticated curl:

```bash
# Get OAuth token first
TOKEN=$(curl -s -X POST \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=password&username=$USER&password=$PASS" \
  https://www.reddit.com/api/v1/access_token \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Search r/CryptoCurrency for BNB mentions, newest first
curl -s -H "Authorization: Bearer $TOKEN" \
     -H "User-Agent: linux:twik-trading-bot:v0.1 (by u/your-throwaway)" \
  "https://oauth.reddit.com/r/CryptoCurrency/search.json?q=BNB&restrict_sr=true&sort=new&t=day&limit=25"
```

### Rate limits

| Mode              | Limit                        |
|-------------------|------------------------------|
| Unauthenticated   | 10 requests/minute           |
| OAuth authenticated | 60 requests/minute         |
| Free tier cap     | ~100 QPM per OAuth client ID |
| Max items/request | 100                          |

Reddit returns rate limit headers on every response:

```
X-Ratelimit-Used: 12
X-Ratelimit-Remaining: 48
X-Ratelimit-Reset: 47        # seconds until window resets
```

### Important headers

Always include a descriptive `User-Agent` — Reddit will 403 generic or missing agents:

```
User-Agent: linux:twik-bnb-signal-bot:v0.1 (by u/your-throwaway)
```

Format convention: `<platform>:<app-id>:<version> (by u/<username>)`

---

## PRAW Quickstart (Python)

PRAW (Python Reddit API Wrapper) wraps the official OAuth API with a clean Python interface.
It handles token refresh, rate limit backoff, and pagination automatically.

### Install

```bash
pip install praw
```

### Init

```python
import praw

# Read-only (sufficient for search/read, no posting needed)
reddit = praw.Reddit(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    user_agent="linux:twik-bnb-signal-bot:v0.1 (by u/your-throwaway)",
)

# Authenticated (needed if you want to vote/comment — not required here)
reddit = praw.Reddit(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    username="your-throwaway",
    password="throwaway-password",
    user_agent="linux:twik-bnb-signal-bot:v0.1 (by u/your-throwaway)",
)
```

Store credentials in `.env` / environment variables, never hardcode.

### Code example — search multiple subs for a token symbol

```python
import praw
import os
from datetime import datetime, timezone

reddit = praw.Reddit(
    client_id=os.environ["REDDIT_CLIENT_ID"],
    client_secret=os.environ["REDDIT_CLIENT_SECRET"],
    user_agent="linux:twik-bnb-signal-bot:v0.1 (by u/your-throwaway)",
)

SUBREDDITS = ["CryptoCurrency", "BNBChainOfficial"]

def fetch_reddit_signals(token_symbol: str, time_filter: str = "day", limit: int = 25):
    """
    Search watchlist token mentions across crypto subreddits.
    Returns list of dicts with title, score, num_comments, url, created_utc.
    """
    results = []
    for sub_name in SUBREDDITS:
        sub = reddit.subreddit(sub_name)
        for post in sub.search(
            query=token_symbol,
            sort="new",
            time_filter=time_filter,
            limit=limit,
        ):
            results.append({
                "subreddit": sub_name,
                "title": post.title,
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "url": f"https://reddit.com{post.permalink}",
                "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
                "selftext_snippet": post.selftext[:300] if post.selftext else "",
            })

    # Sort by newest
    results.sort(key=lambda x: x["created_utc"], reverse=True)
    return results


# Usage
if __name__ == "__main__":
    signals = fetch_reddit_signals("BNB", time_filter="day", limit=25)
    for s in signals[:5]:
        print(f"[{s['subreddit']}] {s['title']} | score={s['score']} | {s['url']}")
```

PRAW handles rate limits internally and will sleep when the limit is hit.
For high-frequency polling, add explicit `time.sleep(1)` between sub searches to stay safe.

---

## Recommendation

For the TWIK trading agent, use a **two-tier strategy**:

| Tier | Tool | When to use |
|------|------|-------------|
| **Primary** | Agent Reach + rdt-cli | Development and local runs. Zero cost, no approval. Fast to set up. |
| **Fallback / Production** | PRAW + Reddit OAuth | When rdt-cli sessions expire, VPS IPs get blocked, or you need reliability SLAs. |

**Practical guidance:**

- Start with Agent Reach for prototyping. Run `agent-reach doctor` before each agent session
  to verify the Reddit channel is live.
- Reddit is a secondary signal — polling once per 5–10 minutes is plenty and keeps you well
  under rate limits on either path.
- When you move to a server/VPS deployment, migrate to PRAW + OAuth. Residential IPs
  rarely get 403'd; VPS ranges are blocked more aggressively by Reddit's CDN.
- Store the throwaway credentials in `.env` and reference via environment variables in both
  rdt-cli and PRAW.

---

## Gotchas

1. **Anonymous 403**: Reddit blocks unauthenticated requests from non-browser user agents.
   Both rdt-cli (cookie auth) and PRAW (OAuth) bypass this — but never attempt raw
   `requests.get("reddit.com/...")` without auth in production.

2. **VPS IP blocking**: Reddit's CDN (Fastly) 403s VPS/datacenter IP ranges more aggressively
   than residential IPs. If deployed on AWS/GCP/DigitalOcean, expect periodic 403s even with
   valid OAuth tokens. Use retry logic with exponential backoff.

3. **rdt-cli cookie expiry**: Sessions are valid ~7 days. For a long-running trading agent,
   add a health check that re-runs `rdt login` (or alerts you) when the session expires.
   This requires a browser on the machine — problematic for headless servers.

4. **Single-maintainer risk**: Both Agent Reach and rdt-cli are maintained by one developer.
   If the project goes unmaintained, the fallback to PRAW is straightforward since it uses
   the official API.

5. **Rate limits are per OAuth client**: If you register multiple apps, each gets its own
   60 req/min bucket. For multi-sub polling across many tokens, batch your queries efficiently.

6. **`after` pagination**: Reddit's `after` cursor is a post fullname (`t3_<id>`). If you
   need more than 100 results, iterate with `after` — but for trading signals, recent + new
   is more valuable than deep pagination.

7. **Reddit API approval (2025)**: As of 2025, Reddit requires agreeing to the Responsible
   Builder Policy and submitting a project description even for personal/script apps. Allow
   a few days for approval. The throwaway account for rdt-cli is separate from this — rdt-cli
   bypasses the official API entirely.

8. **PRAW lazy loading**: PRAW objects don't fetch data until an attribute is accessed.
   Access `.title` or `.score` inside the iteration loop to trigger fetching.

---

## Source URLs

- [Agent Reach GitHub (Panniantong)](https://github.com/Panniantong/Agent-Reach)
- [Agent Reach English README](https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md)
- [Agent Reach CLAUDE.md](https://github.com/Panniantong/Agent-Reach/blob/main/CLAUDE.md)
- [rdt-cli GitHub (public-clis)](https://github.com/public-clis/rdt-cli)
- [Agent Reach review — andrew.ooo](https://andrew.ooo/posts/agent-reach-ai-agent-internet-cli-review/)
- [PRAW Quick Start docs](https://praw.readthedocs.io/en/stable/getting_started/quick_start.html)
- [Reddit API credentials guide 2025 — Wappkit](https://www.wappkit.com/blog/reddit-api-credentials-guide-2025)
- [Reddit API with Python 2024 — JCChouinard](https://www.jcchouinard.com/reddit-api/)
- [Reddit API rate limits — Data365](https://data365.co/blog/reddit-api-limits)
- [Reddit API 2025 crackdown — ReplyDaddy](https://replydaddy.com/blog/reddit-api-pre-approval-2025-personal-projects-crackdown)
- [PRAW scraping guide — DevGenius](https://blog.devgenius.io/scraping-reddit-with-praw-python-reddit-api-wrapper-eaa7d788d7b9)
