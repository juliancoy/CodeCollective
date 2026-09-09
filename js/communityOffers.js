(() => {
  const section = document.getElementById('community-offers');
  if (!section) return;
  const list = document.getElementById('community-offers-list');
  const status = document.getElementById('community-offers-status');
  const more = document.getElementById('community-offers-more');
  const retry = document.getElementById('community-offers-retry');
  const seen = new Set();
  let cursor = null;
  let busy = false;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function portalUrl(value) {
    const url = new URL(value);
    if (url.protocol !== 'https:' || (url.hostname !== 'codecollective.us' && !url.hostname.endsWith('.codecollective.us'))) {
      throw new Error('Invalid offer link');
    }
    return url.href;
  }

  function card(offer) {
    const url = portalUrl(offer.url);
    const li = document.createElement('li');
    const article = element('article', 'community-offer');
    article.dataset.offerId = offer.id;
    const placeholder = element('div', 'community-offer-media community-offer-placeholder', offer.category);
    placeholder.setAttribute('aria-hidden', 'true');
    if (offer.image_url) {
      const photo = element('img', 'community-offer-media');
      photo.src = portalUrl(offer.image_url);
      photo.alt = offer.title;
      photo.loading = 'lazy';
      photo.decoding = 'async';
      photo.addEventListener('error', () => photo.replaceWith(placeholder), { once: true });
      article.append(photo);
    } else article.append(placeholder);
    const content = element('div', 'community-offer-content');
    content.append(element('p', 'community-offer-community', offer.community_name));
    const heading = document.createElement('h3');
    const title = element('a', '', offer.title);
    title.href = url;
    heading.append(title);
    content.append(heading);
    const description = offer.description.length > 180 ? `${offer.description.slice(0, 177)}…` : offer.description;
    content.append(element('p', 'community-offer-description', description));
    const hours = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(offer.minutes / 60);
    content.append(element('p', 'community-offer-meta', `${hours} ${offer.minutes === 60 ? 'hour' : 'hours'} · ${offer.category}`));
    content.append(element('p', 'community-offer-member', `${offer.member_name}${offer.location ? ` · ${offer.location}` : ''}`));
    const link = element('a', 'community-offer-link', 'View offer →');
    link.href = url;
    link.setAttribute('aria-label', `View offer: ${offer.title}`);
    content.append(link);
    article.append(content);
    li.append(article);
    return li;
  }

  async function load() {
    if (busy) return;
    busy = true;
    more.disabled = true;
    retry.hidden = true;
    status.textContent = 'Loading community offers…';
    try {
      const query = cursor ? `?before=${encodeURIComponent(cursor)}` : '';
      const response = await fetch(`/api/org/api/timebank/public-offers${query}`, {
        credentials: 'omit', cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error('Offers unavailable');
      const page = await response.json();
      if (!Array.isArray(page.items)) throw new Error('Invalid offers response');
      const fresh = page.items.filter(offer => !seen.has(offer.id));
      const cards = fresh.map(card);
      list.append(...cards);
      fresh.forEach(offer => seen.add(offer.id));
      cursor = page.next_cursor;
      more.hidden = !cursor;
      status.textContent = seen.size
        ? `${seen.size} public ${seen.size === 1 ? 'offer' : 'offers'} shown.`
        : 'No public offers yet. Share a skill with the community.';
      if (cards.length && seen.size > cards.length) cards[0].querySelector('a').focus();
    } catch {
      status.textContent = seen.size ? 'More offers could not be loaded. Please try again.' : 'Community offers could not be loaded. Please try again.';
      retry.hidden = false;
    } finally {
      busy = false;
      more.disabled = false;
    }
  }
  more.addEventListener('click', load);
  retry.addEventListener('click', load);
  void load();
})();
