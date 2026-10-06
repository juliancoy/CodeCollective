// This Worker has no public routes. Only production frontend service bindings
// can fetch these assets; no session cookies or bearer tokens are forwarded.
export async function previewResponse(request, env) {
  const url = new URL(request.url);
  const headers = { 'cache-control': 'private, no-store', 'x-robots-tag': 'noindex, nofollow, noarchive' };
  if (!['GET', 'HEAD'].includes(request.method) || /^\/(api|pidp|auth|\.well-known)(\/|$)/.test(url.pathname)) {
    return Response.json({ error: 'assets_only' }, { status: 404, headers });
  }
  const mount = request.headers.get('x-preview-mount');
  if (!['lifetech', 'root', 'portal'].includes(mount)) return new Response('Private development asset service', { status: 403, headers });
  const originalPath = url.pathname;
  const navigation = (request.headers.get('accept') || '').includes('text/html') || !originalPath.split('/').at(-1).includes('.');
  let path = mount === 'root' ? `/__portal_root${originalPath}` : originalPath;
  if (path.endsWith('/')) path += 'index.html';
  else if (!path.split('/').at(-1).includes('.')) path += '.html';
  async function asset(pathname) {
    const target = new URL(url);
    target.pathname = pathname;
    return env.ASSETS.fetch(new Request(target, { method: request.method }));
  }
  let response = await asset(path);
  if (response.status === 404 && mount === 'lifetech') {
    if (navigation) response = await asset(`${originalPath.replace(/\/$/, '')}/index.html`);
    if (response.status === 404) response = await asset(`/__portal_root${originalPath}`);
  }
  if (response.status === 404 && navigation) response = await asset(mount === 'portal' ? '/p/index.html' : '/__portal_root/index.html');
  const resultHeaders = new Headers(response.headers);
  for (const [key, value] of Object.entries(headers)) resultHeaders.set(key, value);
  resultHeaders.delete('etag');
  response = new Response(response.body, { status: response.status, headers: resultHeaders });
  if (request.method !== 'HEAD' && (response.headers.get('content-type') || '').includes('text/html')) {
    const stamp = String(env.PREVIEW_REVISION || 'workspace').replace(/[<>&"']/g, '');
    response = new HTMLRewriter()
      .on('head', { element(el) { el.append('<meta name="robots" content="noindex,nofollow,noarchive">', { html: true }); } })
      .on('body', { element(el) { el.prepend(`<aside aria-label="Development preview" style="position:relative;z-index:2147483647;padding:10px 16px;background:#422006;color:#fff;font:14px/1.5 system-ui;text-align:center">Development preview · ${stamp} · Account actions use live services. Switch back in your avatar menu.</aside>`, { html: true }); } })
      .transform(response);
  }
  return response;
}
