// Keep aligned with createAppRouter.tsx; route tests enforce this contract.
const paths = [
  "/local/newsletters",

  "/",
  "/portals/:tenantSlug",
  "/finance",
  "/departments",
  "/ecops",
  "/send",
  "/receive",
  "/create",
  "/create/for-profit",
  "/create/non-profit",
  "/auth/callback",
  "/index.html",
  "/initiatives/:slug",
  "/initiatives/:slug/sign",
  "/org-events",
  "/community",
  "/communities",
  "/medtech-events",
  "/ecosystem/network",
  "/ecosystem/network/webgpu",
  "/ecosystem/network/events",
  "/ecosystem/network/relationships",
  "/ecosystem/network/help",
  "/ecosystem/network/funding",
  "/resources",
  "/branding",
  "/branding.html",
  "/about",
  "/terms",
  "/legal",
  "/email",
  "/email/preferences",
  "/settings/notifications",
  "/android/install",
  "/users/register",
  "/users/login",
  "/users/mcp-connect",
  "/users/dashboard",
  "/profile",
  "/calendar",
  "/calendar.html",
  "/calendar/integrations",
  "/settings",
  "/users/profile",
  "/users/account",
  "/constituent",
  "/constituent/dashboard",
  "/constituent/profile",
  "/constituent/account",
  "/constituent/login",
  "/constituent/register",
  "/id",
  "/orgs/register",
  "/orgs/login",
  "/orgs/initiatives",
  "/orgs/initiatives/editable",
  "/orgs/initiatives/new",
  "/orgs/initiatives/:id/edit",
  "/orgs/initiatives/:id/ballot",
  "/orgs/profile",
  "/orgs/account",
  "/orgs/events",
  "/orgs/events/venues",
  "/orgs/events/venues/:id",
  "/chat",
  "/chat/:roomId",
  "/dev-tools",
  "/tools/business-cards",
  "/admin",
  "/admin/nametags",
  "/admin/ubi-settings",
  "/targets/:target",
  "/meetings",
  "/meetings/:host",
  "/availability",
  "/onboarding",
  "/availability/:id",
  "/following",
  "/events",
  "/events/:slug",
  "/orgs",
  "/people",
  "/timebanking",
  "/life-insurance",
  "/health-insurance",
  "/provider-scheduling",
  "/property-casualty-insurance",
  "/search",
  "/orgs/:handle",
  "/users/:slug",
  "/contact/:slug",
  "/contact-settings",
  "/governance/documents/lifetech-constitution",
  "/governance/documents/lifetech-constitution/tickets/:ticketId",
  "/governance/roberts",
  "/governance/roberts/propose",
  "/governance/roberts/:id",
  "/governance/roberts/:id/amend",
  "/governance",
  "/governance/propose",
  "/governance/:id",
  "/governance/:id/amend"
];
const patterns = paths.map(path => new RegExp('^' + path.split('/').map(part => part.startsWith(':') ? '[^/]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('/') + '/?$'));
export function isPortalPagePath(path) {
  try { return patterns.some(pattern => pattern.test(decodeURIComponent(path))); }
  catch { return false; }
}
export async function missingPortalResource(request, path, apiOrigin) {
  if (['GET', 'HEAD'].includes(request.method) && /^\/orgs\/research-state-maryland\/?$/.test(path)) {
    const target = new URL(request.url);
    target.hostname = 'orgportal.cc';
    target.pathname = '/orgs/state-of-maryland';
    return Response.redirect(target.toString(), 308);
  }
  if (!apiOrigin || !['GET', 'HEAD'].includes(request.method) || path === '/users/me' || paths.includes(path.replace(/\/$/, '') || '/')) return null;
  const match = /^\/(events|orgs|users)\/([^/]+)\/?$/.exec(path);
  if (!match) return null;
  const url = new URL(request.url);
  let slug;
  try { slug = decodeURIComponent(match[2]); } catch { return notFoundResponse(request); }
  try {
    const response = await fetch(`${apiOrigin.replace(/\/$/, '')}/api/network/${match[1]}/public/${encodeURIComponent(slug)}`, {
      headers: { 'x-forwarded-host': url.host, 'x-forwarded-proto': url.protocol.replace(':', '') }, redirect: 'manual',
    });
    if (response.status === 404) return notFoundResponse(request);
    if (response.ok) return null;
  } catch { /* An unavailable API is not evidence that a resource is missing. */ }
  return new Response(request.method === 'HEAD' ? null : 'This page is temporarily unavailable.', { status: 503, headers: { 'cache-control': 'no-store' } });
}
export function notFoundResponse(request) {
  const html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>404 — Page not found</title><meta name="robots" content="noindex"><style>body{font:18px/1.6 system-ui;margin:10vh auto;padding:24px;max-width:640px}a{color:#087b91}</style></head><body><main><h1>404 — Page not found</h1><p>The page you’re looking for does not exist.</p><a href="/">Go home</a></main></body></html>';
  return new Response(request.method === 'HEAD' ? null : html, {status:404,headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-robots-tag':'noindex'}});
}
