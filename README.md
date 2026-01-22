# Substack Friend Finder

Find people with similar interests based on overlap in Substack newsletter subscriptions.

## Browser Extension (Recommended)

The easiest way to use this tool is via the browser extension - no installation or technical setup required.

### Chrome

1. Load the extension from the `extension/` folder (see [extension/README.md](extension/README.md))
2. Go to [substack.com](https://substack.com) and log in
3. Click the extension icon, enter your username, and click "Find Friends"

### Firefox

1. Load the extension from the `extension-firefox/` folder (see [extension-firefox/README.md](extension-firefox/README.md))
2. Go to [substack.com](https://substack.com) and log in
3. Click the extension icon, enter your username, and click "Find Friends"

The extension scans all your subscribed newsletters and finds people with overlapping reading interests. Results are stored locally in your browser.

## CLI Tool

For power users who want more control, there's also a command-line tool.

## How It Works

1. Takes your Substack username as input
2. Fetches your newsletter subscriptions
3. Sorts newsletters by "nicheness" (fewest subscribers first)
4. For each newsletter, fetches both subscribers AND followers
5. Tracks which newsletters each person appears in
6. Ranks matches by nicheness-weighted overlap score (shared niche newsletters count more)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install firefox
```

### 2. Log into Substack

Just log into Substack in Firefox, Chrome, or Safari. The tool automatically extracts cookies from your browser session - no manual setup needed.

## Usage

```bash
python -m src.main <username> [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-newsletters` | 5 | Number of niche newsletters to scan |
| `--subscribers-per-newsletter` | 200 | People to fetch per newsletter (subscribers + followers) |
| `--min-overlap` | 2 | Minimum shared newsletters for a match |
| `--require-bio` | false | Only show users with a bio |
| `--require-publication` | false | Only show users with their own newsletter |
| `--limit` | 20 | Maximum matches to display |
| `--output` / `-o` | - | Save results to a file |

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
- Rate limited with 8-15 second delays between requests (to appear human and avoid being blocked)
- Opens a visible Firefox window (needed to bypass Cloudflare protection)
- Uses 24-hour caching to reduce repeated API calls
