// Substack Friend Finder - Injected Script
// Makes direct API calls to fetch subscriber/follower data

(function() {
  'use strict';

  const API_BASE = 'https://substack.com/api/v1';
  const STATE_KEY = 'sff_scan_state';

  // Fetch subscriber or follower list directly via API
  async function fetchSubscriberList(authorId, listType) {
    const url = `${API_BASE}/user/${authorId}/subscriber-lists?lists=${listType}`;
    console.log(`[SFF] Fetching ${listType} for author ${authorId}`);

    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) {
        console.log(`[SFF] API returned ${response.status} for ${listType}`);
        return null;
      }
      const data = await response.json();
      console.log(`[SFF] Got ${listType} API response`);
      return data;
    } catch (e) {
      console.log(`[SFF] Failed to fetch ${listType}:`, e.message);
      return null;
    }
  }

  // Rate limiting
  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function randomDelay(min = 8000, max = 15000) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  // Send messages to content script -> popup
  function sendProgress(data) {
    window.postMessage({ source: 'substack-friend-finder', type: 'PROGRESS', ...data }, '*');
  }

  function sendComplete(matches) {
    window.postMessage({ source: 'substack-friend-finder', type: 'COMPLETE', matches }, '*');
  }

  function sendError(message) {
    window.postMessage({ source: 'substack-friend-finder', type: 'ERROR', message }, '*');
  }

  // Profile endpoint works fine
  async function getUserProfile(username) {
    const response = await fetch(`${API_BASE}/user/${username}/public_profile`, {
      credentials: 'include'
    });
    if (!response.ok) throw new Error(`Profile fetch failed: ${response.status}`);
    return response.json();
  }

  // Extract users from subscriber-lists API response format
  function extractUsersFromApiResponse(data) {
    const users = [];
    if (!data || !data.subscriberLists) return users;

    for (const list of data.subscriberLists) {
      for (const group of (list.groups || [])) {
        for (const user of (group.users || [])) {
          users.push({
            id: user.id,
            handle: user.handle || user.username,
            name: user.name,
            bio: user.bio,
            photo_url: user.photo_url,
            primaryPublication: user.primaryPublication,
          });
        }
      }
    }
    return users;
  }

  // Get users via direct API call, with fallbacks to __NEXT_DATA__ and DOM
  async function getUsersForPage(authorId, pageType) {
    // 1. Try direct API call first
    const apiData = await fetchSubscriberList(authorId, pageType);
    if (apiData) {
      const users = extractUsersFromApiResponse(apiData);
      if (users.length > 0) {
        console.log(`[SFF] Got ${users.length} users from API for ${pageType}`);
        return users;
      }
    }

    // 2. Try __NEXT_DATA__
    const nextData = document.getElementById('__NEXT_DATA__');
    if (nextData) {
      try {
        const data = JSON.parse(nextData.textContent);
        const pageProps = data?.props?.pageProps;

        const lists = pageProps?.subscriberLists ||
                      pageProps?.initialData?.subscriberLists ||
                      pageProps?.dehydratedState?.queries?.[0]?.state?.data?.subscriberLists;

        if (lists) {
          const users = [];
          for (const list of lists) {
            for (const group of (list.groups || [])) {
              for (const user of (group.users || [])) {
                users.push({
                  id: user.id,
                  handle: user.handle || user.username,
                  name: user.name,
                  bio: user.bio,
                  photo_url: user.photo_url,
                  primaryPublication: user.primaryPublication,
                });
              }
            }
          }
          if (users.length > 0) {
            console.log(`[SFF] Got ${users.length} users from __NEXT_DATA__`);
            return users;
          }
        }
      } catch (e) {
        console.log('[SFF] Could not parse __NEXT_DATA__:', e);
      }
    }

    // 3. Fallback: scrape from visible DOM
    console.log('[SFF] Scraping from DOM...');
    const users = [];
    const profileLinks = document.querySelectorAll('a[href*="/@"]');
    const seenHandles = new Set();

    for (const link of profileLinks) {
      const href = link.getAttribute('href');
      const match = href.match(/@([a-zA-Z0-9_-]+)/);
      if (!match) continue;

      const handle = match[1];
      if (seenHandles.has(handle)) continue;
      seenHandles.add(handle);

      const card = link.closest('[class*="row"]') || link.closest('[class*="Row"]') || link.parentElement?.parentElement;

      users.push({
        id: null,
        handle: handle,
        name: link.textContent?.trim() || handle,
        bio: card?.querySelector('[class*="bio"]')?.textContent?.trim(),
        photo_url: card?.querySelector('img')?.src,
        primaryPublication: null,
      });
    }

    console.log(`[SFF] Got ${users.length} users from DOM`);
    return users;
  }

  // Scoring
  function computeNichenessWeight(subscriberCount) {
    return 1.0 / Math.log((subscriberCount || 1000) + 2);
  }

  function computeQualityScore(profile) {
    let score = 0;
    if (profile.bio) score += 1.0;
    if (profile.primaryPublication) score += 2.0;
    if (profile.photo_url) score += 0.5;
    return score;
  }

  // State management
  function getState() {
    try {
      return JSON.parse(sessionStorage.getItem(STATE_KEY)) || null;
    } catch {
      return null;
    }
  }

  function setState(state) {
    sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
  }

  function clearState() {
    sessionStorage.removeItem(STATE_KEY);
  }

  // Process current page and continue scan
  async function processScan() {
    const state = getState();
    if (!state) {
      console.log('[SFF] No scan state found');
      return;
    }

    const currentPage = state.pagesToVisit[state.currentPageIndex];
    console.log('[SFF] Resuming scan, page:', state.currentPageIndex + 1, '/', state.pagesToVisit.length);

    // Check if we're on the right page
    const url = window.location.href;
    if (currentPage && url.includes(`@${currentPage.subdomain}`)) {
      sendProgress({
        step: 'scanning',
        current: state.currentPageIndex + 1,
        total: state.pagesToVisit.length,
        name: currentPage.name,
        pageType: currentPage.pageType,
        newsletterCount: state.newsletters.length,
        matchCount: Object.keys(state.personAppearances).length
      });

      console.log('[SFF] Fetching data for', currentPage.name, currentPage.pageType);
      const users = await getUsersForPage(currentPage.authorId, currentPage.pageType);
      console.log('[SFF] Got', users.length, 'users');

      // Track appearances
      for (const user of users) {
        if (!user.handle) continue;

        const key = user.handle;
        if (!state.personAppearances[key]) {
          state.personAppearances[key] = {
            profile: user,
            newsletterIds: []
          };
        }
        if (!state.personAppearances[key].newsletterIds.includes(currentPage.newsletterId)) {
          state.personAppearances[key].newsletterIds.push(currentPage.newsletterId);
        }
      }

      state.currentPageIndex++;
      setState(state);
    }

    // Move to next page or finish
    if (state.currentPageIndex < state.pagesToVisit.length) {
      const next = state.pagesToVisit[state.currentPageIndex];
      console.log('[SFF] Moving to:', next.name, next.pageType);

      sendProgress({
        step: 'scanning',
        current: state.currentPageIndex + 1,
        total: state.pagesToVisit.length,
        name: next.name,
        pageType: next.pageType,
        newsletterCount: state.newsletters.length,
        matchCount: Object.keys(state.personAppearances).length
      });

      const delay = randomDelay();
      console.log('[SFF] Waiting', delay, 'ms');
      await sleep(delay);

      window.location.href = `https://substack.com/@${next.subdomain}/${next.pageType}`;
      return;
    }

    // All done
    console.log('[SFF] Scan complete!');
    finishScan(state);
  }

  function finishScan(state) {
    sendProgress({ step: 'status', message: 'Computing matches...' });

    const matches = [];
    const newsletterMap = new Map(state.newsletters.map(n => [n.id, n]));

    for (const [handle, data] of Object.entries(state.personAppearances)) {
      const { profile, newsletterIds } = data;

      // Skip the user themselves
      if (handle.toLowerCase() === state.username.toLowerCase()) continue;

      // Require at least 2 shared newsletters
      if (newsletterIds.length < 2) continue;

      let score = 0;
      const sharedNewsletters = [];

      for (const nlId of newsletterIds) {
        const nl = newsletterMap.get(nlId);
        if (nl) {
          score += computeNichenessWeight(nl.subscriberCount);
          sharedNewsletters.push(nl);
        }
      }

      score += computeQualityScore(profile) * 0.1;

      matches.push({
        user: {
          id: profile.id,
          username: profile.handle || '',
          name: profile.name || profile.handle || '',
          bio: profile.bio || '',
          photoUrl: profile.photo_url || '',
          hasPublication: !!profile.primaryPublication,
          publicationUrl: profile.primaryPublication?.url || ''
        },
        score,
        sharedNewsletters
      });
    }

    matches.sort((a, b) => b.score - a.score);

    clearState();
    console.log('[SFF] Found', matches.length, 'matches');
    sendComplete(matches);
  }

  // Start a new scan
  async function startScan(username) {
    try {
      clearState();
      sendProgress({ step: 'status', message: `Fetching profile for @${username}...` });

      const profile = await getUserProfile(username);
      console.log('[SFF] Got profile:', profile.name);

      const subscriptions = profile.subscriptions || [];
      if (subscriptions.length === 0) {
        throw new Error('No subscriptions found');
      }

      sendProgress({ step: 'status', message: `Found ${subscriptions.length} subscriptions` });

      // Sort by subscriber count (nichest first) - scan ALL newsletters
      const newsletters = subscriptions
        .map(sub => sub.publication)
        .filter(pub => pub && pub.subdomain && (pub.author_id || pub.primary_user_id))
        .sort((a, b) => (a.subscriber_count || 0) - (b.subscriber_count || 0));

      console.log('[SFF] Newsletters to scan:', newsletters.length);

      // Build list of pages to visit: each newsletter has subscribers + followers
      const pagesToVisit = [];
      for (const nl of newsletters) {
        pagesToVisit.push({
          newsletterId: nl.id,
          name: nl.name,
          subdomain: nl.subdomain,
          authorId: nl.author_id || nl.primary_user_id,
          subscriberCount: nl.subscriber_count,
          pageType: 'subscribers'
        });
        pagesToVisit.push({
          newsletterId: nl.id,
          name: nl.name,
          subdomain: nl.subdomain,
          authorId: nl.author_id || nl.primary_user_id,
          subscriberCount: nl.subscriber_count,
          pageType: 'followers'
        });
      }

      // Initialize state
      const state = {
        username,
        profileId: profile.id,
        newsletters: newsletters.map(n => ({
          id: n.id,
          name: n.name,
          subdomain: n.subdomain,
          authorId: n.author_id || n.primary_user_id,
          subscriberCount: n.subscriber_count
        })),
        pagesToVisit,
        currentPageIndex: 0,
        personAppearances: {}
      };

      setState(state);

      // Navigate to first page
      const first = state.pagesToVisit[0];
      sendProgress({
        step: 'scanning',
        current: 1,
        total: state.pagesToVisit.length,
        name: `${first.name} (${first.pageType})`,
        matchCount: 0
      });

      console.log('[SFF] Starting with:', first.name, first.pageType);
      await sleep(randomDelay(2000, 4000));
      window.location.href = `https://substack.com/@${first.subdomain}/${first.pageType}`;

    } catch (error) {
      console.error('[SFF] Error:', error);
      sendError(error.message);
    }
  }

  // Listen for commands
  window.addEventListener('message', function(event) {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== 'substack-friend-finder-command') return;

    console.log('[SFF] Received command:', event.data);

    if (event.data.type === 'START_SCAN') {
      startScan(event.data.username);
    } else if (event.data.type === 'CANCEL_SCAN') {
      console.log('[SFF] Cancelling scan');
      clearState();
    }
  });

  // On load: check if we're resuming a scan
  console.log('[SFF] Injected script loaded');

  const state = getState();
  if (state) {
    console.log('[SFF] Found scan state, resuming...');
    // Small delay to let page render and network requests complete
    setTimeout(processScan, 3000);
  } else {
    window.postMessage({ source: 'substack-friend-finder', type: 'READY' }, '*');
  }

})();
