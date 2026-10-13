import savedPreviews from './eventSourcePreviews.json' with { type: 'json' }

// Resolve missing preview images from supported public event listings only.
function listingUrl(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && ['www.eventbrite.com', 'eventbrite.com'].includes(url.hostname)
      && !url.username && !url.password && !url.port && url.pathname.startsWith('/e/') ? url : null
  } catch { return null }
}

function decodeAttribute(value) {
  return value.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
}

export async function withEventSourcePreview(event, fetchListing = fetch) {
  if (event.social_image_url || event.links?.some(link => link.url === event.source_url && link.image_url)) return event
  const source = listingUrl(event.source_url)
  if (!source) return event
  const savedPreview = savedPreviews[source.href]
  if (savedPreview?.image_url) return { ...event, social_image_url: savedPreview.image_url }
  try {
    const response = await fetchListing(source.href, {
      redirect: 'error', signal: AbortSignal.timeout(4000),
      headers: { accept: 'text/html' }, cf: { cacheEverything: true, cacheTtl: 3600 },
    })
    if (!response.ok || !response.headers.get('content-type')?.includes('text/html') || !response.body) return event
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let html = ''
    let bytes = 0
    try {
      while (bytes < 262144) {
        const { value, done } = await reader.read()
        if (done) break
        bytes += value.byteLength
        if (bytes > 262144) break
        html += decoder.decode(value, { stream: true })
        if (html.includes('</head>')) break
      }
    } finally { await reader.cancel() }
    for (const tag of html.match(/<meta\b[^>]*>/gi) || []) {
      const attributes = Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*(["'])(.*?)\2/g)].map(match => [match[1].toLowerCase(), decodeAttribute(match[3])]))
      if ((attributes.property || attributes.name) !== 'og:image' || !attributes.content) continue
      const image = new URL(attributes.content, source)
      if (image.protocol !== 'https:' || image.username || image.password) continue
      return { ...event, social_image_url: image.href }
    }
  } catch { /* Listing outages must not make the event unavailable. */ }
  return event
}
