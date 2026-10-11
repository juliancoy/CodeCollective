import { useEffect, useState } from 'react';

/**
 * Markdown is rendered with marked and sanitized with DOMPurify, both pulled
 * in on demand: they are only ever needed once a detail sheet is open, so they
 * stay out of the initial payload.
 *
 * 531 of the 1,695 Baltimore descriptions carry markdown or raw HTML, and the
 * longest is 4,514 characters, so this is not an edge case.
 */
export function Description({ markdown }: { markdown: string }) {
  const [html, setHtml] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    if (markdown.trim() === '') return;

    void (async () => {
      try {
        const [{ marked }, DOMPurify] = await Promise.all([
          import('marked'),
          import('dompurify'),
        ]);
        const parsed = await marked.parse(markdown, { async: true, breaks: true, gfm: true });
        const clean = DOMPurify.default.sanitize(parsed, {
          ALLOWED_TAGS: [
            'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'a', 'ul', 'ol', 'li',
            'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
            'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div',
          ],
          ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'target', 'rel'],
          ALLOW_DATA_ATTR: false,
        });
        if (!cancelled) setHtml(clean);
      } catch {
        // Fall back to the plain text rather than showing nothing.
        if (!cancelled) setHtml(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [markdown]);

  if (markdown.trim() === '') return null;

  return (
    <div>
      <div
        className={`prose ${expanded ? '' : 'clamp-6'}`}
        style={{ color: 'var(--ink)' }}
        // Sanitized above; links are forced to open safely by the effect below.
        {...(html !== null
          ? { dangerouslySetInnerHTML: { __html: html } }
          : { children: <p style={{ whiteSpace: 'pre-wrap' }}>{markdown}</p> })}
        ref={(node) => {
          if (!node) return;
          for (const a of node.querySelectorAll('a')) {
            a.setAttribute('target', '_blank');
            a.setAttribute('rel', 'noopener noreferrer nofollow');
          }
        }}
      />
      {!expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="t-meta mt-1"
          style={{ color: 'var(--brand-on-bg)' }}
        >
          Show more
        </button>
      )}
    </div>
  );
}
