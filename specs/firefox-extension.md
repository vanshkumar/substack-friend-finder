# Firefox Extension Spec

## Problem / User Story

As a Firefox user who found this tool useful, I want to install the Substack Friend Finder extension from Firefox Add-ons instead of using Chrome.

## Approach

Port the existing Chrome extension to Firefox. The WebExtensions API is largely compatible, so most code can be reused with minimal changes.

## Key Differences from Chrome

### Manifest Changes

| Chrome (MV3) | Firefox |
|--------------|---------|
| `"manifest_version": 3` | `"manifest_version": 2` (more stable on Firefox) |
| `"background": { "service_worker": "..." }` | `"background": { "scripts": ["..."] }` |
| `"action"` | `"browser_action"` |
| `"host_permissions"` | Merged into `"permissions"` |
| N/A | `"browser_specific_settings"` (required for AMO) |

### API Differences

- Firefox uses `browser.*` namespace (Promise-based)
- Chrome uses `chrome.*` namespace (callback-based)
- Both work in Firefox, but `browser.*` is preferred
- Our code uses `chrome.*` which Firefox supports for compatibility

### No Service Worker

Firefox MV2 uses persistent background scripts, not service workers. This is actually simpler - no execution time limits.

## Requirements

### 1. Create Firefox-specific manifest

```json
{
  "manifest_version": 2,
  "name": "Substack Friend Finder",
  "version": "1.0.0",
  "description": "Find people who share your niche reading interests on Substack",
  "homepage_url": "https://github.com/vanshkumar/substack-friend-finder",
  "browser_specific_settings": {
    "gecko": {
      "id": "substack-friend-finder@vanshkumar",
      "strict_min_version": "109.0"
    }
  },
  "icons": {
    "16": "assets/icon16.png",
    "48": "assets/icon48.png",
    "128": "assets/icon128.png"
  },
  "permissions": [
    "storage",
    "activeTab",
    "*://*.substack.com/*"
  ],
  "browser_action": {
    "default_popup": "src/popup/popup.html",
    "default_icon": {
      "16": "assets/icon16.png",
      "48": "assets/icon48.png"
    }
  },
  "content_scripts": [
    {
      "matches": ["*://*.substack.com/*", "*://substack.com/*"],
      "js": ["src/content/content.js"],
      "run_at": "document_idle"
    }
  ],
  "web_accessible_resources": [
    "src/content/injected.js"
  ],
  "background": {
    "scripts": ["src/background/background.js"]
  }
}
```

### 2. Code Changes

**Background script**: Rename `service-worker.js` to `background.js` (or create Firefox-specific version). The code should work as-is since we're not using service worker-specific APIs.

**All other files**: Should work unchanged. Firefox supports `chrome.*` APIs for compatibility.

### 3. Directory Structure

Option A: Separate directories
```
extension/           # Chrome
extension-firefox/   # Firefox (copy with different manifest)
```

Option B: Build script that generates both from shared source
```
extension/
  src/               # Shared source
  manifest.chrome.json
  manifest.firefox.json
  build.sh           # Copies and renames appropriate manifest
```

**Recommendation**: Option A for simplicity. The code is small enough that maintaining two copies is fine.

### 4. Firefox Add-ons Store Assets

Same as Chrome:
- Icons: 16x16, 48x48, 128x128 (already have)
- Screenshot: At least one
- Privacy policy URL (same as Chrome, already have)

### 5. Submission Requirements

- Firefox Add-ons account (free, no fee unlike Chrome's $5)
- Source code may be requested for review
- Add-on ID in manifest (`browser_specific_settings.gecko.id`)

## Non-Goals

- Safari extension (completely different architecture)
- Manifest V3 on Firefox (less mature than V2)
- Shared build system (overkill for this project size)

## Constraints

- Must maintain feature parity with Chrome extension
- No new dependencies
- Keep code as similar as possible for maintainability

## Acceptance Criteria

- [ ] Firefox extension loads without errors
- [ ] Can enter username and start scan
- [ ] Progress displays correctly
- [ ] Results display with scores and shared newsletters
- [ ] CSV export works
- [ ] State persists when popup is closed and reopened
- [ ] Extension submitted to Firefox Add-ons

## Risks / Unknowns

1. **API compatibility**: Some edge cases may behave differently
   - Mitigation: Test thoroughly in Firefox

2. **Review time**: Firefox reviews can take 1-2 days for new add-ons
   - Mitigation: Submit early, iterate if rejected

3. **Manifest V2 deprecation**: Firefox is moving to V3 eventually
   - Mitigation: V2 will be supported for a long time; can migrate later

## Action Plan

### Phase 1: Port
1. Create `extension-firefox/` directory
2. Copy all source files
3. Create Firefox-specific `manifest.json`
4. Rename service-worker.js to background.js
5. Test locally in Firefox

### Phase 2: Test
1. Load as temporary add-on in Firefox (`about:debugging`)
2. Run full scan and verify results match Chrome
3. Test CSV export
4. Test state persistence

### Phase 3: Submit
1. Create Firefox Add-ons developer account
2. Zip the extension
3. Submit with same description/privacy policy as Chrome
4. Respond to any review feedback

## Definition of Done

- [ ] Extension works identically to Chrome version
- [ ] Published on Firefox Add-ons (addons.mozilla.org)
- [ ] Can be installed by Firefox users with one click
