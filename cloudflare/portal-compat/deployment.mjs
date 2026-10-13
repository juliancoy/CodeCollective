// Frontend selection is a browser preference, never an authorization decision.
export const deploymentPath = '/__portal/deployment'
export const deploymentCookie = '__Host-portal_deployment'

export function selectedDeployment(request, env) {
  const development = (request.headers.get('cookie') || '').split(';').some(part => part.trim() === `${deploymentCookie}=development`)
  return development && env.DEV_ASSETS ? 'development' : 'production'
}

export function isDeploymentAssetRequest(request) {
  const path = new URL(request.url).pathname
  return ['GET', 'HEAD'].includes(request.method) && !request.headers.has('upgrade')
    && !/^\/(?:api|pidp|auth|\.well-known|__portal|health|version)(?:\/|$)/.test(path)
    && !['/robots.txt', '/sitemap.xml', '/push-sw.js', '/__deployment.json'].includes(path)
}

export async function deploymentResponse(request, env, { mount = 'lifetech', enabled = true } = {}) {
  const url = new URL(request.url)
  const available = enabled && Boolean(env.DEV_ASSETS)
  const headers = { 'cache-control': 'no-store', 'vary': 'Cookie' }
  if (url.pathname === deploymentPath) {
    const status = () => ({ mode: selectedDeployment(request, available ? env : {}), available })
    if (request.method === 'GET' || request.method === 'HEAD') {
      return new Response(request.method === 'HEAD' ? null : JSON.stringify(status()), { headers: { ...headers, 'content-type': 'application/json' } })
    }
    if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { ...headers, allow: 'GET, HEAD, POST' } })
    if (request.headers.get('origin') !== url.origin) return Response.json({ error: 'same_origin_required' }, { status: 403, headers })
    let body
    try { body = await request.json() } catch { return Response.json({ error: 'invalid_selection' }, { status: 400, headers }) }
    if (!['production', 'development'].includes(body?.mode)) return Response.json({ error: 'invalid_selection' }, { status: 400, headers })
    if (body.mode === 'development' && !available) return Response.json({ error: 'development_unavailable' }, { status: 503, headers })
    return Response.json({ mode: body.mode, available }, { headers: {
      ...headers,
      'set-cookie': `${deploymentCookie}=${body.mode === 'development' ? 'development' : ''}; Path=/; Max-Age=${body.mode === 'development' ? 7776000 : 0}; HttpOnly; Secure; SameSite=Lax`,
    } })
  }
  if (!available || selectedDeployment(request, env) !== 'development' || !isDeploymentAssetRequest(request)) return null
  // The service gets no member tokens or session cookies: it can only read assets.
  const upstreamHeaders = new Headers({ accept: request.headers.get('accept') || '*/*', 'x-preview-mount': mount })
  const response = await env.DEV_ASSETS.fetch(new Request(request.url, { method: request.method, headers: upstreamHeaders }))
  const resultHeaders = new Headers(response.headers)
  resultHeaders.set('cache-control', 'private, no-store')
  resultHeaders.set('vary', 'Cookie')
  resultHeaders.set('x-robots-tag', 'noindex, nofollow, noarchive')
  resultHeaders.set('x-portal-deployment', 'development')
  resultHeaders.delete('set-cookie')
  return new Response(response.body, { status: response.status, headers: resultHeaders })
}

export function deploymentCachePolicy(response, env) {
  if (!env.DEV_ASSETS || response.status === 101) return response
  const headers = new Headers(response.headers)
  const vary = headers.get('vary') || ''
  if (!vary.split(',').some(part => part.trim().toLowerCase() === 'cookie')) headers.set('vary', vary ? `${vary}, Cookie` : 'Cookie')
  if ((headers.get('content-type') || '').includes('text/html')) headers.set('cache-control', 'private, no-store')
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers })
}
