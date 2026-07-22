// Shared, dependency-free formatting helpers used across dashboards.

export function formatCurrency(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

export function formatPercent(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return `${n.toFixed(1)}%`;
}

export function initials(name) {
  if (!name) return '?';
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

// Splits `text` on **bold** markers into { text, bold } segments. Used to
// render mock chat responses with emphasis without ever touching
// dangerouslySetInnerHTML — the mock engine only ever wraps plain
// extracted figures, but this keeps the rendering path safe regardless.
export function parseInlineEmphasis(text) {
  if (!text) return [];
  return text.split(/(\*\*[^*]+\*\*)/g).map((part) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return { text: part.slice(2, -2), bold: true };
    }
    return { text: part, bold: false };
  });
}

// Short local clock time for chat message timestamps (e.g. "3:42 PM").
export function formatTime(timestamp) {
  if (!timestamp) return '';
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

// Format an ISO timestamp as "Jul 21, 2026  3:42 PM"
export function formatDateTime(timestamp) {
  if (!timestamp) return '—';
  try {
    const d = new Date(timestamp);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      + '  ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '—';
  }
}

export function titleCase(value) {
  if (!value) return '';
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
