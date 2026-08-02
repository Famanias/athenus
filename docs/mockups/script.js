/* ==============================================================================
   ATHENUS KNOWLEDGE OS — PROTOTYPE INTERACTIVE LOGIC
   Vanilla JavaScript — Interactive UI Navigator & Mock State Engine
   ============================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initWorkspaceTabs();
  initCommandPalette();
  initFlashcardFlip();
  initQuizScoring();
  initInteractiveTranscript();
});

/* 1. Global Navigation & View Switching */
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  const views = document.querySelectorAll('.view-panel');
  const viewTitle = document.getElementById('active-view-title');

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.getAttribute('data-view');
      if (!targetView) return;

      navItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      views.forEach(v => {
        if (v.id === `view-${targetView}`) {
          v.classList.remove('hidden');
        } else {
          v.classList.add('hidden');
        }
      });

      if (viewTitle) {
        viewTitle.textContent = item.querySelector('.nav-label')?.textContent || 'Workspace';
      }
    });
  });
}

/* 2. Workspace Sub-Tabs Switching */
function initWorkspaceTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabViews = document.querySelectorAll('.tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      if (!targetTab) return;

      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      tabViews.forEach(v => {
        if (v.id === `tab-${targetTab}`) {
          v.classList.remove('hidden');
        } else {
          v.classList.add('hidden');
        }
      });
    });
  });
}

/* 3. Command Palette Modal (Ctrl+K / Cmd+K) */
function initCommandPalette() {
  const modal = document.getElementById('command-palette-overlay');
  const trigger = document.getElementById('cmd-palette-trigger');
  const input = document.getElementById('command-input');
  const resultsContainer = document.getElementById('command-results');

  function openModal() {
    if (modal) {
      modal.classList.remove('hidden');
      if (input) input.focus();
    }
  }

  function closeModal() {
    if (modal) modal.classList.add('hidden');
  }

  if (trigger) trigger.addEventListener('click', openModal);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (modal && modal.classList.contains('hidden')) {
        openModal();
      } else {
        closeModal();
      }
    }
    if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
      closeModal();
    }
  });

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  // Simulated search filtering
  if (input && resultsContainer) {
    input.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      const items = resultsContainer.querySelectorAll('.command-result-item');
      items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(query)) {
          item.style.display = 'flex';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }
}

/* 4. Flashcard Flip Interaction */
function initFlashcardFlip() {
  const cards = document.querySelectorAll('.flashcard-item');
  cards.forEach(card => {
    card.addEventListener('click', () => {
      card.classList.toggle('flipped');
    });
  });
}

/* 5. Quiz Interactive Scoring */
function initQuizScoring() {
  const options = document.querySelectorAll('.quiz-option');
  options.forEach(opt => {
    opt.addEventListener('click', () => {
      const parent = opt.closest('.quiz-question-box');
      if (!parent) return;

      parent.querySelectorAll('.quiz-option').forEach(o => {
        o.classList.remove('selected', 'correct', 'incorrect');
      });

      const isCorrect = opt.getAttribute('data-correct') === 'true';
      if (isCorrect) {
        opt.classList.add('correct');
      } else {
        opt.classList.add('incorrect');
      }
    });
  });
}

/* 6. Interactive Transcript Click-to-Seek */
function initInteractiveTranscript() {
  const paras = document.querySelectorAll('.transcript-para');
  paras.forEach(para => {
    para.addEventListener('click', () => {
      paras.forEach(p => p.classList.remove('active'));
      para.classList.add('active');

      const time = para.getAttribute('data-timestamp');
      const timeDisplay = document.getElementById('current-video-time');
      if (timeDisplay && time) {
        timeDisplay.textContent = time;
      }
    });
  });
}

/* 7. Simulated Video Playback Seek */
function seekToTimestamp(timestampStr) {
  const timeDisplay = document.getElementById('current-video-time');
  if (timeDisplay) timeDisplay.textContent = timestampStr;

  // Switch to Video tab if not active
  const videoTabBtn = document.querySelector('.tab-btn[data-tab="video"]');
  if (videoTabBtn) videoTabBtn.click();
}
