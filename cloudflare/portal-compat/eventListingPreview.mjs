// Reuse supplied listing metadata without fetching arbitrary third-party sites.
export function eventListingPreview(event, origin) {
  const externalLinks = (Array.isArray(event.links) ? event.links : []).filter(link => {
    try { const target = new URL(link.url); return ['http:', 'https:'].includes(target.protocol) && target.origin !== origin }
    catch { return false }
  })
  const listing = externalLinks.find(link => link.url === event.source_url) || externalLinks[0]
  return {
    title: event.social_title || listing?.title || event.title,
    description: event.social_description || listing?.description || event.description,
    image: event.social_image_url || (listing?.image_url ? new URL(listing.image_url, listing.url).href : null) || event.flyer_urls?.social || event.image_url,
    externalImage: !event.social_image_url && !!listing?.image_url,
    externalTitle: !event.social_title && !!listing?.title,
  }
}
