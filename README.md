# Substack Friend Finder

Find people with similar interests based on overlap in Substack newsletter subscriptions.

## How It Works

1. Takes your Substack username as input
2. Fetches the newsletters you subscribe to
3. For each newsletter, fetches other subscribers
4. Gets each subscriber's own subscriptions
5. Ranks matches by overlap, weighted by "nicheness" (smaller newsletters count more)

## Setup

### 1. Install dependencies

```bash
pip install playwright rich requests browser_cookie3
python -m playwright install chromium
```

### 2. Log into Substack

Just log into Substack in Firefox, Chrome, or Safari. The tool automatically pulls cookies from your browser - no manual setup needed.

## Usage

```bash
python -m src.main <username> [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-newsletters` | 5 | Number of newsletters to scan |
| `--subscribers-per-newsletter` | 50 | Subscribers to fetch per newsletter |
| `--min-overlap` | 2 | Minimum shared subscriptions for a match |
| `--require-bio` | false | Only show users with a bio |
| `--require-publication` | false | Only show users with their own newsletter |
| `--limit` | 20 | Maximum matches to display |

### Examples

```bash
# Basic usage
python -m src.main johndoe

# Scan more newsletters, require users have publications
python -m src.main johndoe --max-newsletters 10 --require-publication

# Find highly-overlapping matches only
python -m src.main johndoe --min-overlap 5 --subscribers-per-newsletter 100
```

## Output

The tool displays ranked matches with:
- **Score**: Nicheness-weighted overlap (niche newsletters count more)
- **Shared newsletters**: Which subscriptions you have in common
- **Bio**: User's profile description (if available)
- **Profile URL**: Link to their Substack profile
- **Publication URL**: Link to their newsletter (if they have one)

## Scoring

Matches are scored using nicheness-weighted overlap:

```
score = Σ (1 / log(subscriber_count + 2))
```

This means:
- A shared niche newsletter (1,000 subscribers) counts more than a popular one (100,000 subscribers)
- Multiple shared newsletters accumulate

## Limitations

- Requires being subscribed to newsletters to see their subscriber lists
- Rate limited to ~1 request/second to avoid being blocked
- Opens a browser window (needed to bypass Cloudflare)
