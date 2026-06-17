# twitterapi.io — Developer Reference

> **Purpose:** Social signal source for autonomous trading agent. One batched query per 15-min cycle across a ~25-token watchlist. Hard budget ≤1,000 calls/day.
>
> **Last verified:** June 2026 from live docs and pricing pages (sources at bottom).

---

## 1. Overview

twitterapi.io is a pay-per-call REST wrapper around Twitter/X data. It bypasses the official X API entirely — no Twitter developer account needed, just a twitterapi.io API key. It gives access to tweet search, user profiles, follower data, and more at ~96% lower cost than the official X API.

**Why we use it:**
- `$0.00015` per tweet fetched (15 credits, where 100,000 credits = $1 USD)
- Per call returns up to 20 tweets → each call costs `~$0.003`
- At ≤1,000 calls/day: max daily spend ≈ **$3.00/day** ($0.003 × 1,000)
- In our 25-token / 15-min cycle model: ~96 calls/day → ~**$0.29/day**
- No rate cap in the traditional sense — 1,000+ queries/second supported

---

## 2. Auth

All requests require an API key passed as a **request header**.

| Header name | Format |
|-------------|--------|
| `X-API-Key` | `YOUR_API_KEY_STRING` (plain string, no "Bearer" prefix) |

**Getting your key:**
1. Sign up at https://twitterapi.io (Google sign-in gives free starter credits)
2. Dashboard → copy API key
3. Set it as env var: `TWITTER_API_KEY=your_key_here`

**Do NOT** put the key in code. Use env var or secrets manager.

---

## 3. Tweet / Advanced Search Endpoint

### Endpoint

```
GET https://api.twitterapi.io/twitter/tweet/advanced_search
```

### Query Parameters

| Parameter | Type | Required | Values / Notes |
|-----------|------|----------|----------------|
| `query` | string | **YES** | Search expression — see query syntax below |
| `queryType` | string | **YES** | `"Latest"` or `"Top"` — use `"Latest"` for recency-based signal |
| `cursor` | string | No | Pagination token; omit or pass `""` for the first page |

### Query Syntax for Cashtags

The `query` parameter supports Twitter's full advanced search operator set:

```
# Single cashtag
$BTC

# Multiple cashtags — use OR (uppercase required)
$BTC OR $ETH OR $SOL

# Grouped cashtags (parentheses OK)
($BTC OR $ETH OR $SOL OR $BNB OR $AVAX)

# Exclude retweets to reduce noise
($BTC OR $ETH) -filter:retweets

# Language filter
($BTC OR $ETH) lang:en

# Exclude retweets AND replies, English only
($BTC OR $ETH OR $SOL) -filter:retweets -filter:replies lang:en

# Date-windowed (Unix timestamps)
($BTC OR $ETH) since_time:1718000000 until_time:1718003600
```

**Supported operators (partial list):**

| Operator | Example | Notes |
|----------|---------|-------|
| `OR` | `$BTC OR $ETH` | Must be uppercase |
| `AND` | `$BTC AND bitcoin` | Implicit when terms space-separated |
| `-term` | `-filter:retweets` | Negation / exclusion |
| `from:` | `from:elonmusk` | Tweets from a specific user |
| `#hashtag` | `#bitcoin` | Hashtag filter |
| `$cashtag` | `$BTC` | Cashtag filter |
| `lang:` | `lang:en` | Language filter (ISO 639-1) |
| `since:` | `since:2024-01-01` | Date filter (YYYY-MM-DD) |
| `until:` | `until:2024-01-02` | Date filter (YYYY-MM-DD) |
| `since_time:` | `since_time:1718000000` | Unix timestamp (more precise) |
| `until_time:` | `until_time:1718003600` | Unix timestamp (more precise) |
| `min_faves:` | `min_faves:100` | Min likes (web operator) |
| `min_retweets:` | `min_retweets:10` | Min retweets (web operator) |
| `has:media` | `has:media` | Tweets with any media |
| `filter:retweets` | `-filter:retweets` | Filter/exclude retweets |
| `filter:replies` | `-filter:replies` | Filter/exclude replies |
| `is:verified` | `is:verified` | Verified accounts only |

> **[UNVERIFIED] Query string length limit:** No explicit character limit is documented. In practice, a 25-cashtag OR chain (e.g., `$BTC OR $ETH OR $SOL OR ... OR $TOKEN25`) is well within any reasonable URL length limit (~500–600 chars). Test empirically with your full watchlist.

> **[UNVERIFIED] Operator naming gotcha:** The web uses `min_faves:` / `min_retweets:`, but some API contexts expect `min_likes:` / `min_reposts:`. This **fails silently** (no error, just no results). Stick to `-filter:retweets` style operators for reliability.

---

## 4. Batching Strategy for a 25-Token Watchlist

### The Core Idea

Twitter's OR operator lets you combine your entire watchlist into **one query string**. One API call = one credit charge = mentions for all 25 tokens at once.

### Recommended Query Template

```python
WATCHLIST = [
    "$BTC", "$ETH", "$SOL", "$BNB", "$AVAX",
    "$MATIC", "$ARB", "$OP", "$LINK", "$UNI",
    # ... up to 25 tokens
]

def build_watchlist_query(tokens: list[str], exclude_retweets: bool = True) -> str:
    joined = " OR ".join(tokens)
    query = f"({joined})"
    if exclude_retweets:
        query += " -filter:retweets"
    return query

# Example output:
# ($BTC OR $ETH OR $SOL OR ...) -filter:retweets
```

### Per-Cycle Budget Math

| Metric | Value |
|--------|-------|
| Cycle interval | 15 min |
| Calls per cycle | 1 (batched) |
| Cycles per day | 96 |
| **Calls per day** | **96** |
| Cost per call | ~$0.003 (20 tweets × $0.00015) |
| **Daily cost** | **~$0.29** |
| Budget headroom (≤1,000 calls/day) | 10× — safe for retries + burst |

### Counting Mentions Per Token

After fetching, parse the response locally — no extra API calls needed:

```python
from collections import Counter

def count_mentions(tweets: list[dict], tokens: list[str]) -> Counter:
    counts = Counter()
    for tweet in tweets:
        text = tweet["text"].upper()
        for token in tokens:
            if token.upper() in text:
                counts[token] += 1
    return counts
```

---

## 5. Response Shape

### Full Response (200 OK)

```json
{
  "tweets": [
    {
      "type": "tweet",
      "id": "1234567890123456789",
      "url": "https://twitter.com/i/web/status/1234567890123456789",
      "text": "$BTC just broke resistance — bulls are back 🚀",
      "createdAt": "2024-06-14T10:30:00.000Z",
      "retweetCount": 42,
      "replyCount": 7,
      "likeCount": 183,
      "author": {
        "type": "user",
        "userName": "cryptotrader99",
        "id": "987654321"
      }
    }
  ],
  "has_next_page": true,
  "next_cursor": "some_opaque_cursor_string"
}
```

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `tweets` | array | Up to 20 tweet objects per page; may be fewer (ads filtered) |
| `tweets[].text` | string | Full tweet text — parse this for cashtag mentions |
| `tweets[].createdAt` | string | ISO 8601 timestamp |
| `tweets[].retweetCount` | integer | Retweet count at time of fetch |
| `tweets[].likeCount` | integer | Like count at time of fetch |
| `tweets[].replyCount` | integer | Reply count at time of fetch |
| `tweets[].author.userName` | string | Twitter handle (no @ prefix) |
| `has_next_page` | boolean | Whether more pages exist |
| `next_cursor` | string | Pass to `cursor` param for next page |

> **[UNVERIFIED] Additional fields:** The docs show a minimal schema above. The actual response likely includes more fields (quote count, bookmark count, media URLs, etc.) — inspect a live response to confirm the full shape.

### Error Response (400)

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "Query parameter is required"
  }
}
```

---

## 6. Pricing Per Read

| Unit | Cost |
|------|------|
| 1 credit | $0.00001 USD |
| 100,000 credits | $1.00 USD |
| 1 tweet fetched | 15 credits = **$0.00015** |
| 1 API call (up to 20 tweets) | ~300 credits = **~$0.003** |
| 1,000 tweets fetched | $0.15 |
| 1M tweets fetched | $150 |

**Billing model:** Prepaid credits, never expire. No subscription required. Optional $99/month auto-recharge plan for convenience (rates identical).

**Free tier:** Sign up with Google → starter credits (one-time, for evaluation).

---

## 7. Rate Limits

| Limit type | Value |
|------------|-------|
| Requests per second | 1,000+ (default) |
| Daily call cap | None documented (budget-limited by credits) |
| Per-minute cap | None documented |
| Higher limits | Available on request |

**In practice:** At ≤1,000 calls/day spread across 96 cycles, you are nowhere near any throughput limit. The effective limit is your credit balance.

> **[UNVERIFIED] No hard per-day limit** is documented beyond credit depletion. If credits run out, calls return 402 or similar — implement balance monitoring.

---

## 8. GetXAPI Comparison

| Feature | twitterapi.io | GetXAPI |
|---------|--------------|---------|
| Price per call (~20 tweets) | ~$0.003 | $0.001 |
| Price per 1,000 tweets | $0.15 | $0.05 |
| Relative cost | 3× more expensive | Cheaper |
| Endpoints | 60+ (communities, spaces, DMs) | 35+ |
| Response time | 500–800 ms | <2 s |
| OR batching | Supported | Supported |
| Webhooks / WebSocket | Yes | [UNVERIFIED] |
| Auth header | `X-API-Key` | [UNVERIFIED - check their docs] |
| Free signup credits | Yes | Yes |

**Bottom line for this project:** GetXAPI is 3× cheaper per call. At our volume (~96 calls/day), twitterapi.io costs ~$0.29/day vs. GetXAPI's ~$0.096/day — a $70/year difference. If cost becomes a concern, GetXAPI is the primary alternative to evaluate. twitterapi.io has the edge in endpoint breadth and documented reliability.

---

## 9. Code Examples

### curl

```bash
# Single cashtag
curl -G "https://api.twitterapi.io/twitter/tweet/advanced_search" \
  -H "X-API-Key: $TWITTER_API_KEY" \
  --data-urlencode "query=\$BTC -filter:retweets lang:en" \
  --data-urlencode "queryType=Latest"

# Batched 25-token watchlist
curl -G "https://api.twitterapi.io/twitter/tweet/advanced_search" \
  -H "X-API-Key: $TWITTER_API_KEY" \
  --data-urlencode "query=(\$BTC OR \$ETH OR \$SOL OR \$BNB OR \$AVAX) -filter:retweets lang:en" \
  --data-urlencode "queryType=Latest"
```

### Python

```python
import os
import requests
from collections import Counter

TWITTERAPI_BASE = "https://api.twitterapi.io/twitter"
API_KEY = os.environ["TWITTER_API_KEY"]

WATCHLIST = [
    "$BTC", "$ETH", "$SOL", "$BNB", "$AVAX",
    "$MATIC", "$ARB", "$OP", "$LINK", "$UNI",
    # ... add up to 25 tokens
]


def build_query(tokens: list[str]) -> str:
    joined = " OR ".join(tokens)
    return f"({joined}) -filter:retweets lang:en"


def fetch_mentions(tokens: list[str], cursor: str = "") -> dict:
    """
    Single batched call for all tokens.
    Returns raw API response dict.
    """
    response = requests.get(
        f"{TWITTERAPI_BASE}/tweet/advanced_search",
        headers={"X-API-Key": API_KEY},
        params={
            "query": build_query(tokens),
            "queryType": "Latest",
            "cursor": cursor,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def count_mentions(tweets: list[dict], tokens: list[str]) -> Counter:
    counts = Counter()
    for tweet in tweets:
        text = tweet["text"].upper()
        for token in tokens:
            if token.upper() in text:
                counts[token] += 1
    return counts


def get_mention_snapshot(tokens: list[str]) -> Counter:
    """
    One 15-min cycle: one API call, count mentions per token.
    Does NOT paginate — single page is sufficient for velocity signal.
    """
    data = fetch_mentions(tokens)
    tweets = data.get("tweets", [])
    return count_mentions(tweets, tokens)


# Usage
if __name__ == "__main__":
    snapshot = get_mention_snapshot(WATCHLIST)
    print(snapshot.most_common(10))
```

### Mention Velocity (across cycles)

```python
from collections import deque
import time

# Rolling window: keep last N snapshots
WINDOW_SIZE = 4  # 4 × 15 min = 1-hour velocity

history: deque[Counter] = deque(maxlen=WINDOW_SIZE)


def compute_velocity(current: Counter, history: deque) -> Counter:
    """Velocity = current mentions - oldest snapshot in window."""
    if len(history) < 2:
        return current
    oldest = history[0]
    return Counter({token: current[token] - oldest.get(token, 0)
                    for token in current})


# In your trading loop:
while True:
    snapshot = get_mention_snapshot(WATCHLIST)
    history.append(snapshot)
    velocity = compute_velocity(snapshot, history)
    # Use velocity to weight signals...
    time.sleep(900)  # 15 minutes
```

---

## 10. Gotchas

1. **`OR` must be uppercase.** `$BTC or $ETH` will treat `or` as a literal search term. Always `OR`.

2. **Operator naming mismatch (silent failure).** Web-style `min_faves:` / `min_retweets:` may not work via API; use `-filter:retweets` style. Silent failure — no 400 error, just empty/wrong results.

3. **Up to 20 tweets per page, not exactly 20.** Ads are filtered server-side, so you may get 17–20 results. Don't assume 20 for cost math.

4. **Credits deplete silently if not monitored.** Implement a balance check in your agent startup. A depleted balance likely returns a 402 or 401 — confirm exact error code from a test.

5. **`queryType` is required.** Omitting it may cause a 400. Always pass `"Latest"` for recency-based mention counting.

6. **URL-encode the query.** The `query` param contains special chars (`$`, `(`, `)`, spaces). Use `requests.get(..., params={...})` in Python (handles encoding automatically), or `--data-urlencode` in curl. Do NOT manually concatenate into the URL.

7. **No pagination needed for velocity signal.** Page 1 (~20 most recent tweets) is sufficient for a 15-min cycle. Paginating only costs more credits and adds latency.

8. **Cashtag vs. hashtag.** `$BTC` and `#BTC` are different on Twitter. This project uses cashtag (`$`) — confirm your watchlist tokens are commonly posted as cashtags (most crypto tokens are).

9. **`createdAt` is ISO 8601, not Unix.** Parse with `datetime.fromisoformat()` or `dateutil.parser.parse()`. Not all Python versions handle the trailing `Z` natively — use `replace("Z", "+00:00")` for compatibility.

10. **[UNVERIFIED] No documented per-day hard cap** on calls beyond credit depletion. But budget defensively — wrap all calls in try/except and check HTTP status for 402/429.

---

## 11. Source URLs

- [twitterapi.io Advanced Search API Reference](https://docs.twitterapi.io/api-reference/endpoint/tweet_advanced_search) — endpoint URL, params, auth header, response schema
- [twitterapi.io Complete Search Guide 2025](https://twitterapi.io/blog/twitter-search-api-complete-guide-2025) — OR operator syntax, cashtag examples
- [Searching for a Tweet — Operators Reference](https://twitterapi.io/blog/search-a-tweet) — full operator list, silent failure gotcha
- [twitterapi.io Pricing Blog](https://twitterapi.io/blog/twitter-api-pricing) — credit system, $0.00015/tweet, $99/month auto-recharge
- [twitterapi.io README / Overview](https://twitterapi.io/readme) — auth setup, base URL, 1,000 QPS claim
- [GetXAPI vs twitterapi.io Comparison](https://www.getxapi.com/getxapi-vs-twitterapi-io) — pricing differential, feature table, DM endpoint note
- [GetXAPI Twitter API Alternatives Page](https://www.getxapi.com/twitter-api-alternatives) — broader alternative landscape
