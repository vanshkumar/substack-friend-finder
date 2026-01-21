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
5. Wait 3-5 minutes while it scans your niche newsletters

### Project Structure

```
extension/
├── manifest.json           # Chrome extension config
├── src/
│   ├── popup/              # Extension popup UI
│   │   ├── popup.html
│   │   ├── popup.js
│   │   └── popup.css
│   ├── content/            # Content script (runs on substack.com)
│   │   └── content.js
│   └── background/         # Service worker
│       └── service-worker.js
└── assets/                 # Icons (TODO: add before publishing)
```

## TODO Before Publishing

- [ ] Create extension icons (16x16, 48x48, 128x128)
- [ ] Add promotional images for Chrome Web Store
- [ ] Write privacy policy
- [ ] Test on multiple accounts

## How It Works

1. Content script runs on `substack.com` pages
2. When you click "Find Friends", it:
   - Fetches your subscriptions (public)
   - Sorts by subscriber count (nichest first)
   - For each niche newsletter, fetches followers/subscribers (authenticated)
   - Scores people by how many of your niche newsletters they also follow
3. Results are cached locally in the browser
4. No data is ever sent to any external server
