// Fieldline Dispatch Console — small client-side helpers.
// No external data calls here; purely cosmetic / UX sugar.

function updateClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  const now = new Date();
  const opts = { weekday: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' };
  el.textContent = now.toLocaleString('en-US', opts);
}
updateClock();
setInterval(updateClock, 1000);

// Make any element with data-href behave like a clickable row (used on tables)
document.addEventListener('click', function (e) {
  const row = e.target.closest('[data-href]');
  if (row && !e.target.closest('a, button, input, select, textarea, form')) {
    window.location.href = row.getAttribute('data-href');
  }
});

// Confirm before destructive-ish actions (override, complete)
document.addEventListener('submit', function (e) {
  const form = e.target;
  if (form && form.dataset && form.dataset.confirm) {
    if (!window.confirm(form.dataset.confirm)) {
      e.preventDefault();
    }
  }
});
