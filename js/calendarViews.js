// View switches keep the city, while each view owns its own filter parameters.
window.syncCalendarViewLinks = function () {
  const city = new URLSearchParams(window.location.search).get('city') || 'baltimore';
  document.querySelectorAll('[data-calendar-view]').forEach(link => {
    const url = new URL(link.href, window.location.href);
    url.searchParams.set('city', city);
    link.href = url.pathname + url.search;
  });
};
window.syncCalendarViewLinks();
document.addEventListener('click', event => {
  if (event.target.closest('[data-calendar-view]')) window.syncCalendarViewLinks();
});
window.addEventListener('popstate', window.syncCalendarViewLinks);
