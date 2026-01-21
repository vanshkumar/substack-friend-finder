// Substack Friend Finder - Popup Script

const STORAGE_KEY = 'substackFriendFinder';
const SCAN_STATE_KEY = 'substackFriendFinderScanState';

// DOM Elements
const formSection = document.getElementById('form-section');
const progressSection = document.getElementById('progress-section');
const resultsSection = document.getElementById('results-section');
const notSubstackSection = document.getElementById('not-substack');

const usernameInput = document.getElementById('username');
const startBtn = document.getElementById('start-btn');
const errorMsg = document.getElementById('error-msg');

const progressStatus = document.getElementById('progress-status');
const progressDetail = document.getElementById('progress-detail');
const progressFill = document.getElementById('progress-fill');

const matchCount = document.getElementById('match-count');
const resultsList = document.getElementById('results-list');
const rescanBtn = document.getElementById('rescan-btn');
const cancelBtn = document.getElementById('cancel-btn');
const exportBtn = document.getElementById('export-btn');

// Store all matches for export (not just displayed ones)
let allMatches = [];

// State
let currentTabId = null;
let isScanning = false;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Check if we're on a Substack page
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab.id;

  const isSubstack = tab.url && (
    tab.url.includes('substack.com') ||
    tab.url.match(/https?:\/\/[^/]+\.substack\.com/)
  );

  if (!isSubstack) {
    showSection('not-substack');
    return;
  }

  // Check if scan is in progress
  const scanState = await loadScanState();
  if (scanState && scanState.inProgress) {
    // Check if scan state is stale (older than 1 hour)
    const ONE_HOUR = 60 * 60 * 1000;
    if (scanState.timestamp && (Date.now() - scanState.timestamp > ONE_HOUR)) {
      console.log('[SFF Popup] Clearing stale scan state');
      await clearScanState();
    } else {
      showSection('progress');
      // Restore progress display
      const nlCount = scanState.newsletterCount || Math.ceil(scanState.total / 2);
      const nlIndex = Math.ceil(scanState.current / 2);
      progressStatus.textContent = `Scanning newsletter ${nlIndex} of ${nlCount}`;
      progressDetail.textContent = scanState.name || '';
      if (scanState.matchCount > 0) {
        progressDetail.textContent += ` (${scanState.matchCount} candidates)`;
      }
      progressFill.style.width = `${(scanState.current / scanState.total) * 100}%`;
      return;
    }
  }

  // Check for cached results
  const cached = await loadResults();
  if (cached && cached.matches && cached.matches.length > 0) {
    displayResults(cached.matches, cached.timestamp);
    showSection('results');
  } else {
    showSection('form');
  }
});

// Event Listeners
startBtn.addEventListener('click', startScan);
rescanBtn.addEventListener('click', () => {
  showSection('form');
});

cancelBtn.addEventListener('click', async () => {
  // Clear scan state in popup
  await clearScanState();
  isScanning = false;

  // Tell content script to clear its state too
  try {
    await chrome.tabs.sendMessage(currentTabId, { type: 'CANCEL_SCAN' });
  } catch (e) {
    // Ignore if content script not available
  }

  showSection('form');
});

exportBtn.addEventListener('click', () => {
  if (allMatches.length === 0) return;
  exportMatchesToCSV(allMatches);
});

usernameInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') startScan();
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PROGRESS') {
    handleProgress(message);
  } else if (message.type === 'COMPLETE') {
    handleComplete(message.matches);
  } else if (message.type === 'ERROR') {
    handleError(message.message);
  }
});

// Functions
function showSection(section) {
  formSection.classList.add('hidden');
  progressSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  notSubstackSection.classList.add('hidden');

  switch (section) {
    case 'form':
      formSection.classList.remove('hidden');
      break;
    case 'progress':
      progressSection.classList.remove('hidden');
      break;
    case 'results':
      resultsSection.classList.remove('hidden');
      break;
    case 'not-substack':
      notSubstackSection.classList.remove('hidden');
      break;
  }
}

async function startScan() {
  const username = usernameInput.value.trim().replace('@', '');

  if (!username) {
    showError('Please enter your Substack username');
    return;
  }

  hideError();
  isScanning = true;

  // Clear any old scan state before starting
  await clearScanState();

  showSection('progress');
  progressStatus.textContent = 'Starting scan...';
  progressDetail.textContent = '';
  progressFill.style.width = '0%';

  // Send message to content script
  try {
    await chrome.tabs.sendMessage(currentTabId, {
      type: 'START_SCAN',
      username
    });
  } catch (e) {
    handleError('Could not connect to Substack page. Please refresh and try again.');
  }
}

function handleProgress(progress) {
  console.log('[SFF Popup] Progress:', progress);
  if (progress.step === 'status') {
    progressStatus.textContent = progress.message;
    progressDetail.textContent = '';
    // Save scan state
    saveScanState({ inProgress: true, status: progress.message });
  } else if (progress.step === 'scanning') {
    const nlCount = progress.newsletterCount || Math.ceil(progress.total / 2);
    const nlIndex = Math.ceil(progress.current / 2);
    progressStatus.textContent = `Scanning newsletter ${nlIndex} of ${nlCount}`;
    progressDetail.textContent = progress.name;
    progressFill.style.width = `${(progress.current / progress.total) * 100}%`;

    if (progress.matchCount > 0) {
      progressDetail.textContent += ` (${progress.matchCount} candidates)`;
    }

    // Save scan state
    saveScanState({
      inProgress: true,
      current: progress.current,
      total: progress.total,
      name: progress.name,
      newsletterCount: nlCount,
      matchCount: progress.matchCount || 0
    });
  }
}

async function handleComplete(matches) {
  isScanning = false;

  // Clear scan state
  await clearScanState();

  // Save results
  await saveResults(matches);

  // Display results
  displayResults(matches);
  showSection('results');
}

async function handleError(message) {
  isScanning = false;
  await clearScanState();
  showSection('form');
  showError(message);
}

function displayResults(matches, timestamp) {
  // Store all matches for export
  allMatches = matches;
  matchCount.textContent = `(${matches.length})`;

  if (matches.length === 0) {
    resultsList.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No matches found. Try scanning more newsletters.</p>';
    return;
  }

  resultsList.innerHTML = matches.slice(0, 50).map(match => {
    const { user, score, sharedNewsletters } = match;
    const sharedNames = sharedNewsletters.map(n => n.name).join(', ');
    const bioSnippet = user.bio ? user.bio.substring(0, 100) + (user.bio.length > 100 ? '...' : '') : '';

    return `
      <div class="match-card" data-url="https://substack.com/@${user.username}">
        <div class="match-header">
          <img class="match-avatar" src="${user.photoUrl || 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23eee%22 width=%22100%22 height=%22100%22/></svg>'}" alt="">
          <div>
            <div class="match-name">${escapeHtml(user.name || user.username)}</div>
            <div class="match-username">@${escapeHtml(user.username)}</div>
          </div>
          <div class="match-score">${score.toFixed(2)}</div>
        </div>
        <div class="match-shared">Shared: ${escapeHtml(sharedNames)}</div>
        ${bioSnippet ? `<div class="match-bio">${escapeHtml(bioSnippet)}</div>` : ''}
      </div>
    `;
  }).join('');

  // Add click handlers
  resultsList.querySelectorAll('.match-card').forEach(card => {
    card.addEventListener('click', () => {
      chrome.tabs.create({ url: card.dataset.url });
    });
  });

  // Show timestamp if available
  if (timestamp) {
    const date = new Date(timestamp);
    const ago = getTimeAgo(date);
    const existingNote = resultsList.querySelector('.timestamp-note');
    if (!existingNote) {
      resultsList.insertAdjacentHTML('afterbegin',
        `<p class="timestamp-note" style="font-size: 11px; color: #999; margin-bottom: 8px;">Last scanned: ${ago}</p>`
      );
    }
  }
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.classList.remove('hidden');
}

function hideError() {
  errorMsg.classList.add('hidden');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function getTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
  return `${Math.floor(seconds / 86400)} days ago`;
}

function exportMatchesToCSV(matches) {
  // CSV header
  const headers = ['Rank', 'Name', 'Username', 'Score', 'Shared Newsletters', 'Bio', 'Profile URL', 'Has Publication', 'Publication URL'];

  // CSV rows
  const rows = matches.map((match, index) => {
    const { user, score, sharedNewsletters } = match;
    return [
      index + 1,
      user.name || '',
      user.username || '',
      score.toFixed(3),
      sharedNewsletters.map(n => n.name).join('; '),
      (user.bio || '').replace(/[\n\r]+/g, ' '),
      `https://substack.com/@${user.username}`,
      user.hasPublication ? 'Yes' : 'No',
      user.publicationUrl || ''
    ];
  });

  // Escape CSV values
  const escapeCSV = (value) => {
    const str = String(value);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  // Build CSV content
  const csvContent = [
    headers.map(escapeCSV).join(','),
    ...rows.map(row => row.map(escapeCSV).join(','))
  ].join('\n');

  // Create and download file
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `substack-matches-${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

// Storage functions
async function saveResults(matches) {
  await chrome.storage.local.set({
    [STORAGE_KEY]: {
      matches,
      timestamp: Date.now()
    }
  });
}

async function loadResults() {
  const data = await chrome.storage.local.get(STORAGE_KEY);
  return data[STORAGE_KEY] || null;
}

async function saveScanState(state) {
  await chrome.storage.local.set({ [SCAN_STATE_KEY]: { ...state, timestamp: Date.now() } });
}

async function loadScanState() {
  const data = await chrome.storage.local.get(SCAN_STATE_KEY);
  return data[SCAN_STATE_KEY] || null;
}

async function clearScanState() {
  await chrome.storage.local.remove(SCAN_STATE_KEY);
}
