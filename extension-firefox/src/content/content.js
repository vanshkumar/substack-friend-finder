// Substack Friend Finder - Content Script
// Bridges between popup and injected page script

(function() {
  'use strict';

  let injectedReady = false;
  let pendingCommand = null;

  // Inject the main script into page context
  function injectMainScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('src/content/injected.js');
    script.onload = function() { this.remove(); };
    (document.head || document.documentElement).appendChild(script);
    console.log('[SFF Content] Injected script at', document.readyState);
  }

  // Inject immediately
  injectMainScript();

  // Listen for messages from injected script
  window.addEventListener('message', function(event) {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== 'substack-friend-finder') return;

    const { type, ...rest } = event.data;

    if (type === 'READY') {
      console.log('[SFF Content] Injected script ready');
      injectedReady = true;
      // If there's a pending command, send it now
      if (pendingCommand) {
        window.postMessage(pendingCommand, '*');
        pendingCommand = null;
      }
      return;
    }

    // Forward progress/complete/error to popup via chrome.runtime
    console.log('[SFF Content] Forwarding to popup:', type, rest);

    // Also save scan state directly to storage (in case popup is closed)
    if (type === 'PROGRESS') {
      const progress = rest;
      if (progress.step === 'scanning') {
        const nlCount = progress.newsletterCount || Math.ceil(progress.total / 2);
        chrome.storage.local.set({
          substackFriendFinderScanState: {
            inProgress: true,
            current: progress.current,
            total: progress.total,
            name: progress.name,
            newsletterCount: nlCount,
            matchCount: progress.matchCount || 0,
            timestamp: Date.now()
          }
        });
      }
    } else if (type === 'COMPLETE') {
      // Save results and clear scan state
      chrome.storage.local.set({
        substackFriendFinder: {
          matches: rest.matches,
          timestamp: Date.now()
        }
      });
      chrome.storage.local.remove('substackFriendFinderScanState');
      console.log('[SFF Content] Saved', rest.matches.length, 'matches to storage');
    } else if (type === 'ERROR') {
      // Clear scan state on error
      chrome.storage.local.remove('substackFriendFinderScanState');
    }

    chrome.runtime.sendMessage({ type, ...rest });
  });

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[SFF Content] Received from popup:', message);

    if (message.type === 'START_SCAN') {
      const command = {
        source: 'substack-friend-finder-command',
        type: 'START_SCAN',
        username: message.username
      };

      if (injectedReady) {
        window.postMessage(command, '*');
      } else {
        console.log('[SFF Content] Injected not ready, queuing command');
        pendingCommand = command;
      }

      sendResponse({ status: 'started' });
      return true;
    }

    if (message.type === 'PING') {
      sendResponse({ status: 'ready', injectedReady });
      return true;
    }

    if (message.type === 'CANCEL_SCAN') {
      window.postMessage({
        source: 'substack-friend-finder-command',
        type: 'CANCEL_SCAN'
      }, '*');
      sendResponse({ status: 'cancelled' });
      return true;
    }
  });

  console.log('[SFF Content] Content script loaded');
})();
