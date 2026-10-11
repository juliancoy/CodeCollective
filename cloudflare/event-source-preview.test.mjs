import { test } from 'node:test'
import assert from 'node:assert/strict'
import { withEventSourcePreview } from '../../OrgPortal/web/eventSourcePreview.mjs'
const event = { source_url: 'https://www.eventbrite.com/e/example-123', social_image_url: null }
test('imports Eventbrite social image and decodes query entities', async () => {
  const result = await withEventSourcePreview(event, async () => new Response('<head><meta content="https://img.evbuc.com/pitch.jpg?w=940&amp;q=75" property="og:image"></head>', { headers: { 'content-type': 'text/html' } }))
  assert.equal(result.social_image_url, 'https://img.evbuc.com/pitch.jpg?w=940&q=75')
  assert.equal(event.social_image_url, null)
})
test('retains explicit preview images and does not fetch unsupported hosts', async () => {
  const noFetch = () => { throw new Error('Unexpected fetch') }
  const explicit = { ...event, social_image_url: '/custom.jpg' }
  assert.equal(await withEventSourcePreview(explicit, noFetch), explicit)
  const unsupported = { source_url: 'https://localhost/e/example' }
  assert.equal(await withEventSourcePreview(unsupported, noFetch), unsupported)
})
test('listing failures and oversized HTML preserve event availability', async () => {
  assert.equal(await withEventSourcePreview(event, async () => { throw new Error('timeout') }), event)
  assert.equal(await withEventSourcePreview(event, async () => new Response('x'.repeat(262145), { headers: { 'content-type': 'text/html' } })), event)
})
test('public event API and page metadata use the same source preview', async t => {
  const { default: worker } = await import('./worker.js')
  t.mock.method(globalThis, 'fetch', async url => {
    if (url === 'https://org.example/api/portal/tenant') return Response.json({ id: 'lifetech' })
    if (url === 'https://org.example/api/network/events/public/pitch') return Response.json({ ...event, title: 'Pitch', slug: 'pitch', organization_name: 'Amplify MedTech' })
    if (url === event.source_url) return new Response('<meta property="og:image" content="https://img.evbuc.com/pitch.jpg">', { headers: { 'content-type': 'text/html' } })
    throw new Error(`Unexpected fetch ${url}`)
  })
  const env = { ORG_API_ORIGIN: 'https://org.example', ORGPORTAL_TENANT_HOSTS: 'lifetech.fyi', ASSETS: { fetch: async () => new Response('<html><head></head><body></body></html>', { headers: { 'content-type': 'text/html' } }) } }
  const response = await worker.fetch(new Request('https://lifetech.fyi/api/org/api/network/events/public/pitch'), env)
  assert.equal((await response.json()).social_image_url, 'https://img.evbuc.com/pitch.jpg')
  const page = await worker.fetch(new Request('https://lifetech.fyi/events/pitch', { headers: { accept: 'text/html' } }), env)
  assert.match(await page.text(), /property="og:image" content="https:\/\/img.evbuc.com\/pitch.jpg/)
})
test('verified preview cache supplies the pitch image when Eventbrite blocks edge requests', async () => {
  const result = await withEventSourcePreview({ source_url: 'https://www.eventbrite.com/e/medtech-pitch-competition-tickets-1998508613060' }, () => { throw new Error('Blocked by listing provider') })
  assert.equal(new URL(result.social_image_url).hostname, 'www.eventbrite.com')
  assert.match(result.social_image_url, /1193184895/)
})
