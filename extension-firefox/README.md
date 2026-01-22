# Substack Friend Finder - Firefox Extension

A Firefox extension that helps you find people who share your niche reading interests on Substack.

## Development

### Load Temporary Add-on

1. Open Firefox and go to `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on..."
3. Select the `manifest.json` file in this directory

### Testing

1. Go to [substack.com](https://substack.com) and make sure you're logged in
2. Click the extension icon
3. Enter your Substack username
4. Click "Find Friends"
5. Keep the Substack tab open while scanning (takes 8-15 seconds per newsletter page)

### Project Structure

```
extension-firefox/
├── manifest.json           # Firefox extension config (Manifest V2)
├── src/
│   ├── popup/              # Extension popup UI
│   │   ├── popup.html
│   │   ├── popup.js
│   │   └── popup.css
│   ├── content/            # Scripts running on substack.com
│   │   ├── content.js      # Bridge between popup and injected script
│   │   └── injected.js     # Core logic (runs in page context with cookies)
│   └── background/         # Background script
│       └── background.js
└── assets/                 # Extension icons
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## Differences from Chrome Version

- Uses Manifest V2 (more stable on Firefox)
- Uses `browser_action` instead of `action`
- Uses background script instead of service worker
- Host permissions are in `permissions` array (not separate)
- Includes `browser_specific_settings` for Firefox Add-ons

## How It Works

Same as Chrome version - see main extension README for details.
