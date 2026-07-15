/**
 * QualGen.ai brand logo — SVG recreation of the official mark.
 *
 * Props:
 *   height   — controls overall size (default 32px); width scales automatically
 *   textDark — when true the wordmark renders in dark navy (light backgrounds)
 *              when false the wordmark renders white (dark backgrounds)
 *   iconOnly — renders just the icon, no wordmark
 */
export default function QualGenLogo({ height = 32, textDark = true, iconOnly = false }) {
  // Icon height drives the proportional icon width
  const iconH = height;
  const iconW = iconH * 0.78;   // icon viewBox is ~48×58 → ratio ≈ 0.83, trimmed for visual balance

  const wordmarkSize = height * 0.64;
  const wordmarkColor = textDark ? '#0F172A' : '#FFFFFF';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: height * 0.28, flexShrink: 0 }}>

      {/* ── Icon ───────────────────────────────────────────────────────── */}
      <svg
        viewBox="0 0 48 58"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ height: iconH, width: iconW, flexShrink: 0, display: 'block' }}
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="qg-ring" x1="0" y1="0" x2="48" y2="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#A855F7" />
            <stop offset="100%" stopColor="#6D28D9" />
          </linearGradient>
          <linearGradient id="qg-diamond" x1="24" y1="32" x2="24" y2="58" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#7C3AED" />
            <stop offset="100%" stopColor="#5B21B6" />
          </linearGradient>
        </defs>

        {/* Outer ring — full circle, thick stroke */}
        <circle
          cx="24"
          cy="21"
          r="16"
          stroke="url(#qg-ring)"
          strokeWidth="5.5"
          fill="none"
        />

        {/* Small accent dot — sits at the 10 o'clock position of the ring,
            gives the logo its distinctive "open" character */}
        <circle
          cx="10.5"
          cy="9.5"
          r="4"
          fill="#8B5CF6"
        />

        {/* Downward diamond — the "tail" of the mark, hangs from the bottom of the ring */}
        <path
          d="M24 33 L32 44 L24 56 L16 44 Z"
          fill="url(#qg-diamond)"
        />
      </svg>

      {/* ── Wordmark ────────────────────────────────────────────────────── */}
      {!iconOnly && (
        <div style={{
          display: 'flex',
          alignItems: 'baseline',
          lineHeight: 1,
          flexShrink: 0,
          userSelect: 'none',
        }}>
          <span style={{
            color: wordmarkColor,
            fontSize: wordmarkSize,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
          }}>
            QualGen
          </span>
          <span style={{
            color: '#7C3AED',
            fontSize: wordmarkSize,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
          }}>
            .ai
          </span>
        </div>
      )}
    </div>
  );
}
