# Substack Friend Finder - Browser Extension

A Chrome extension that helps you find people who share your niche reading interests on Substack.

## Development

### Load Unpacked Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select this `extension/` directory

### Testing

1. Go to [substack.com](https://substack.com) and make sure you're logged in
2. Click the extension icon
3. Enter your Substack username
4. Click "Find Friends"
5. Keep the Substack tab open while scanning (takes 8-15 seconds per newsletter page)

### Project Structure

```
extension/
├── manifest.json           # Chrome extension config (Manifest V3)
├── src/
│   ├── popup/              # Extension popup UI
│   │   ├── popup.html
│   │   ├── popup.js
│   │   └── popup.css
│   ├── content/            # Scripts running on substack.com
│   │   ├── content.js      # Bridge between popup and injected script
│   │   └── injected.js     # Core logic (runs in page context with cookies)
│   └── background/         # Service worker
│       └── service-worker.js
└── assets/                 # Extension icons
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## Chrome Web Store Checklist

- [x] Create extension icons (16x16, 48x48, 128x128)
- [x] Write privacy policy (PRIVACY.md)
- [ ] Add promotional images for Chrome Web Store
- [ ] Take screenshots for store listing
- [ ] Create Chrome Web Store developer account ($5)
- [ ] Submit for review

## How It Works

1. Injected script runs in the page context on `substack.com` (with cookie access)
2. When you click "Find Friends", it:
   - Fetches your subscriptions via public profile API
   - Sorts newsletters by subscriber count (nichest first)
   - For each newsletter, calls the subscriber-lists API for subscribers AND followers
   - Tracks which newsletters each person appears in
   - Scores people using nicheness-weighted overlap (shared niche newsletters count more)
   - Filters to people with 2+ shared newsletters
3. Progress and results are saved to `chrome.storage.local`
4. No data is ever sent to any external server - everything stays in your browser
