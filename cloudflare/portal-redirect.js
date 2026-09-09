const CANONICAL_PORTAL = "https://codecollective.us/p";

export function canonicalPortalUrl(requestUrl) {
  const source = new URL(requestUrl);
  const destination = new URL(CANONICAL_PORTAL);

  destination.pathname = source.pathname === "/"
    ? "/p/"
    : `/p${source.pathname}`;
  destination.search = source.search;

  return destination;
}

export default {
  fetch(request) {
    return Response.redirect(canonicalPortalUrl(request.url), 308);
  },
};
