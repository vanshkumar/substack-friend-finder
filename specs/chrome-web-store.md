# Chrome Web Store Submission Spec

## Problem / User Story

As a user who found this extension useful, I want to install it easily from the Chrome Web Store rather than loading it as an unpacked extension in developer mode.

## Requirements

### 1. Developer Account
- [ ] Create Chrome Web Store developer account ($5 one-time fee)
- [ ] Verify identity

### 2. Extension Assets

#### Icons (Required)
- [ ] 16x16 PNG - toolbar icon
- [ ] 48x48 PNG - extensions management page
- [ ] 128x128 PNG - Chrome Web Store listing

#### Store Listing Images
- [ ] At least 1 screenshot (1280x800 or 640x400)
- [ ] Small promo tile (440x280) - optional but recommended
- [ ] Marquee promo tile (1400x560) - optional

### 3. Privacy Policy (Required)
Chrome Web Store requires a privacy policy URL. Need to create and host one.

**Key points to cover:**
- What data is collected (Substack usernames, subscription data)
- Where data is stored (locally in browser only)
- What data is NOT collected (no analytics, no external servers)
- No data sharing with third parties

**Options for hosting:**
- GitHub Pages (free, simple)
- GitHub repo markdown file (link directly)
- Notion public page

### 4. Store Listing Content

#### Extension Name
"Substack Friend Finder" (24 char limit for short name)

#### Summary (132 chars max)
"Find people who share your niche reading interests based on overlapping Substack subscriptions."

#### Description (16,000 chars max)
```
Find people with similar interests based on your Substack newsletter subscriptions.

HOW IT WORKS
1. Enter your Substack username
2. The extension scans your subscribed newsletters
3. For each newsletter, it finds other subscribers and followers
4. People who appear in multiple of your niche newsletters are surfaced as matches
5. Matches are ranked by a "nicheness" score - shared small newsletters count more than big ones

FEATURES
• Scans ALL your subscribed newsletters
• Finds subscribers AND followers of each newsletter
• Nicheness-weighted scoring (niche newsletters count more)
• Export all matches to CSV for further analysis
• Progress saves automatically - close and reopen anytime
• 100% private - all data stays in your browser

PRIVACY
• No data is ever sent to external servers
• No analytics or tracking
• All data stored locally in your browser
• Open source: [GitHub URL]

TIPS
• Keep the Substack tab open while scanning
• Scanning takes 8-15 seconds per newsletter (to avoid rate limits)
• Results are cached - rescan anytime to refresh
```

#### Category
"Productivity" or "Social & Communication"

### 5. Manifest.json Updates

Current manifest needs:
- [ ] Add `icons` field with all icon sizes
- [ ] Verify `description` is good
- [ ] Consider if `homepage_url` should be added (GitHub repo)

### 6. Permissions Justification

Chrome may ask to justify permissions. Current permissions:
- `storage` - Save scan progress and results locally
- `activeTab` - Communicate with the Substack tab
- `host_permissions: *://*.substack.com/*` - Access Substack APIs

All are minimal and necessary.

## Non-Goals
- Paid features / monetization
- Firefox Add-ons store (can do later)
- Safari extension (different process entirely)

## Risks / Unknowns

1. **Review time**: Chrome Web Store review can take days to weeks
2. **Rejection risk**: May be rejected for:
   - Scraping concerns (we use official APIs though)
   - Privacy policy issues
   - Misleading description
3. **Substack ToS**: Verify this doesn't violate Substack's terms
   - We only access data the user could access manually
   - No automation of account actions
   - Read-only operations

## Action Plan

### Phase 1: Assets
1. Create extension icons (can use simple design tool or AI)
2. Take screenshots of extension in action
3. Create promo images (optional)

### Phase 2: Privacy & Legal
1. Write privacy policy
2. Host it (GitHub Pages recommended)
3. Review Substack ToS for compliance

### Phase 3: Store Listing
1. Update manifest.json with icons
2. Prepare all listing content
3. Create developer account
4. Submit for review

### Phase 4: Post-Launch
1. Monitor reviews/feedback
2. Respond to any issues
3. Plan updates based on feedback

## Definition of Done
- [ ] Extension published on Chrome Web Store
- [ ] Privacy policy live and linked
- [ ] Can be installed by anyone with one click
