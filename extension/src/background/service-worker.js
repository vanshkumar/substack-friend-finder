// Substack Friend Finder - Service Worker
// Minimal background script for message routing

chrome.runtime.onInstalled.addListener(() => {
  console.log('Substack Friend Finder installed');
});

// Forward messages between popup and content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Messages from content script get forwarded to popup (if open)
  // Messages from popup go directly to content script via tabs.sendMessage
  // This is mostly a passthrough for progress updates

  return false; // Don't keep channel open
});
