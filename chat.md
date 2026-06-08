# Code Collective Chat Architecture

This document describes a Cloudflare-native chat architecture for Code Collective. The goal is a professional, responsive messaging system that is cheap to operate, simple to iterate on, and not dependent on Arkavo or a long-running Matrix server.

## Current Implementation

The first Cloudflare-native backend boundary is implemented in `portal/chat-worker/`.

- Hono Worker API for authenticated chat routes.
- D1 migration for conversations, members, messages, attachments, and receipts.
- Idempotent message sends with `client_message_id`.
- Per-conversation monotonic `sequence` values.
- `/sync?afterSequence=` catch-up endpoint.
- Durable Object class for active hibernating WebSocket fanout by conversation.
- PIdP bearer-token authentication through `/auth/me`.
- Optional `CONTACTS_DB` binding to resolve public ID/contact slugs into user IDs.
- Native portal chat API client and chat page for conversations, `/chat?start=dm&user=...`, hibernating WebSocket receive acceleration, sequence sync, adaptive polling fallback, optimistic sends, and pending/failed/confirmed message states.
- Matrix chat page remains available with `VITE_CHAT_BACKEND=matrix`.
- Selenium Docker smoke test added for two independent robot accounts logging in through the UI and exchanging messages.
- Node test coverage for auth, direct-message creation/reuse, idempotent sends, sequence sync, message persistence, listing, and read receipts.

This is not mixed into the existing org worker. The portal UI talks to the chat worker through the main site proxy at `/api/chat/*`, which forwards to the standalone chat worker.

The current implementation is a deployable native chat slice. The next production-hardening pass should expand group/org room support, add attachments, and run the two-robot Selenium smoke regularly in CI or a scheduled live-test environment.

## Goals

- Provide direct messages from public ID/profile pages.
- Support organization and event chat rooms.
- Keep Code Collective identity as the source of truth through PIdP.
- Store messages durably in Code Collective-controlled infrastructure.
- Deliver live updates when possible without making realtime availability a correctness requirement.
- Support optimistic, retry-safe client UX.
- Keep the design migration-ready for Matrix or another protocol later.
- Stay within Cloudflare free/low-cost usage where practical.

## Core Principle

Professional chat should have three separate paths:

- **Correctness path:** authenticated HTTP writes, durable database storage, idempotent client message IDs, and cursor sync.
- **Fast path:** Durable Object hibernating WebSocket fanout for active users, with SSE or long-poll as optional future fallback.
- **Offline path:** local pending queue, retry, catch-up sync, and later push notifications.

The database is the source of truth. Realtime delivery is an acceleration layer. If a WebSocket notification is missed, the client must still recover through sync.

## Recommended Stack

- **Cloudflare Worker**
  - Owns the HTTP API.
  - Performs authentication, authorization, validation, rate limiting, and moderation checks.

- **Cloudflare Durable Objects**
  - One Durable Object per conversation.
  - Holds active WebSocket connections for that conversation using Cloudflare WebSocket Hibernation.
  - Broadcasts new messages, receipts, typing state, and presence events as best-effort realtime fanout.
  - Does not replace the durable database or cursor sync.

- **Cloudflare D1**
  - Source of truth for users, conversations, memberships, messages, receipts, and moderation state.

- **Cloudflare R2**
  - Stores uploaded attachments and generated thumbnails.

- **Cloudflare Queues**
  - Optional async work: push notifications, link previews, media scanning, digest emails, retention cleanup.

- **Cloudflare KV**
  - Optional short-lived cache for public profile lookups, room metadata, feature flags, and rate-limit hints.

## High-Level Shape

```text
Portal Web / Mobile Client
  |
  | HTTPS writes + sync, optional WebSocket/SSE
  v
Cloudflare Chat Worker
  |
  | auth + permission checks
  |
  v
D1: conversations, members, messages, receipts
  ^
  |
  | best-effort fanout after durable write
  |
Conversation Durable Object
  |
  | active WebSocket/SSE clients
  v
Portal Web / Mobile Client
```

Attachments are stored separately in R2. The database stores attachment metadata and message references.

## Transport Priority

Clients should prefer the best available transport, but never depend on it for correctness:

1. WebSocket through a per-conversation Durable Object.
2. SSE or long-poll fallback for one-way realtime delivery.
3. Adaptive polling against `/sync`.
4. Web Push or native push notifications for inactive/offline users.

Polling should be adaptive, not constant:

- Focused chat: every 1-2 seconds.
- Recent activity: every 2-5 seconds.
- Hidden tab: every 15-60 seconds.
- Offline: stop polling, then sync immediately when back online.

Add jitter so many clients do not poll at the same instant.

## Core Data Model

### `chat_conversations`

- `id`
- `kind`: `dm`, `org_room`, `event_room`, `system`
- `title`
- `slug`
- `created_by_user_id`
- `org_id`
- `event_id`
- `created_at`
- `updated_at`
- `last_message_at`
- `archived_at`

### `chat_conversation_members`

- `conversation_id`
- `user_id`
- `role`: `owner`, `admin`, `member`
- `state`: `active`, `invited`, `blocked`, `left`
- `joined_at`
- `last_read_message_id`
- `last_read_at`
- `muted_until`

### `chat_messages`

- `id`
- `conversation_id`
- `sender_user_id`
- `client_message_id`
- `body`
- `sequence`
- `message_type`: `text`, `image`, `file`, `system`
- `attachment_id`
- `reply_to_message_id`
- `thread_root_message_id`
- `created_at`
- `edited_at`
- `deleted_at`
- `moderation_state`

`client_message_id` should be generated by the client and unique per sender. The database should enforce `UNIQUE(sender_user_id, client_message_id)` so a retry returns the original canonical message instead of inserting a duplicate.

`sequence` should be assigned by the server and monotonic within each conversation. Sync should use `afterSequence`, not timestamps, to avoid clock skew and ordering bugs.

### `chat_attachments`

- `id`
- `owner_user_id`
- `r2_key`
- `file_name`
- `content_type`
- `byte_size`
- `width`
- `height`
- `created_at`

### `chat_message_receipts`

- `conversation_id`
- `message_id`
- `user_id`
- `receipt_type`: `delivered`, `read`
- `created_at`

## API Surface

### Conversations

- `GET /api/org/api/network/chat/conversations`
- `POST /api/org/api/network/chat/dm`
- `GET /api/org/api/network/chat/conversations/:conversationId`
- `POST /api/org/api/network/chat/conversations/:conversationId/join`
- `POST /api/org/api/network/chat/conversations/:conversationId/leave`

### Messages

- `GET /api/org/api/network/chat/conversations/:conversationId/messages?afterSequence=&limit=`
- `POST /api/org/api/network/chat/conversations/:conversationId/messages`
- `PATCH /api/org/api/network/chat/messages/:messageId`
- `DELETE /api/org/api/network/chat/messages/:messageId`

Message sends should include a client-generated ID:

```json
{
  "client_message_id": "uuid-generated-by-client",
  "body": "hello"
}
```

The server should return the canonical message:

```json
{
  "id": "server-message-id",
  "client_message_id": "same-client-id",
  "conversation_id": "conversation-id",
  "sender_user_id": "pidp-user-id",
  "body": "hello",
  "created_at": "2026-06-07T20:00:00.000Z",
  "sequence": 1842
}
```

### Sync

- `GET /api/org/api/network/chat/conversations/:conversationId/sync?afterSequence=1842`

Sync returns messages, receipts, and relevant room state after the last confirmed sequence. Clients should call sync after reconnects, after failed realtime delivery, and periodically while active.

### Realtime

- `GET /api/org/api/network/chat/conversations/:conversationId/socket`

This upgrades to a Cloudflare hibernating WebSocket after PIdP authentication and membership authorization. Browser clients authenticate the WebSocket with a `pidp.<base64url-token>` subprotocol because browsers cannot send an `Authorization` header during a WebSocket handshake. Ordinary HTTP routes continue to use `Authorization: Bearer <pidp-token>`.

### Receipts

- `POST /api/org/api/network/chat/conversations/:conversationId/read`

### Attachments

- `POST /api/org/api/network/chat/attachments/upload-url`
- `POST /api/org/api/network/chat/attachments/commit`

## Direct Message Flow

Public ID page inbox button:

```text
User clicks inbox icon
  |
  v
POST /api/org/api/network/chat/dm
  { target_user_slug: "julian-coy" }
  |
  v
Worker authenticates caller through PIdP
  |
  v
Worker resolves target user from D1 contact page
  |
  v
Worker finds or creates a dm conversation
  |
  v
Client navigates to /chat/:conversationId
```

The route `/chat?start=dm&user=:slug` can remain as a friendly frontend entrypoint, but the real authority should be the backend `POST /chat/dm` endpoint.

## Durable Object Design

Use one Durable Object instance per conversation:

```text
ConversationDurableObject("conversation:{id}")
```

Responsibilities:

- Accept WebSocket upgrades after the Worker verifies membership.
- Store user/conversation metadata as WebSocket attachments.
- Use `state.acceptWebSocket`, `webSocketMessage`, `webSocketClose`, and `webSocketError` so Cloudflare can hibernate idle sockets.
- Broadcast new-message notifications to connected members after the HTTP write succeeds.
- Broadcast typing indicators and presence as ephemeral state.
- Recover cleanly after restart because D1 and `/sync` are authoritative.

Durable Objects should not be treated as the write authority. If a Durable Object restart or broadcast failure loses an event, clients catch up from D1 using `/sync`.

## Message Send Flow

```text
Client
  |
  | POST /messages with client_message_id
  v
Chat Worker validates auth + membership
  |
  | idempotent insert
  v
D1 insert chat_messages with sequence
  |
  | best-effort notify
  v
Conversation Durable Object
  |
  | fanout message.created
  v
Connected clients reconcile by sequence
  |
  | async side effects
  v
Queue: push notifications, previews, moderation
```

The HTTP `POST /messages` endpoint is the primary send path. WebSocket and SSE are delivery accelerators, not the write path.

## Client UX

The sender should see a message immediately as pending. The UI then reconciles against the canonical server response:

```text
pending -> confirmed
pending -> failed -> retry
```

Retries reuse the same `client_message_id`. That makes optimistic UX safe instead of duplicate-prone.

Clients should keep the latest confirmed `sequence` per conversation. On page load, reconnect, visibility change, and network recovery, they should call `/sync?afterSequence=...`.

Typing and presence are ephemeral:

- Typing state expires after roughly 5 seconds.
- Presence expires after roughly 30 seconds.
- Neither belongs in the durable message log.

## Responsive Frontend Architecture

The chat UI should be built as a dense operational interface, not a marketing page.

Expected views:

- Conversation list
- Message timeline
- Composer
- Room/profile info drawer
- Attachment preview
- Empty state
- Offline/reconnecting state
- Pending/sent/failed message states

Mobile behavior:

- Default to conversation list.
- Selecting a conversation opens the timeline full-screen.
- Back button returns to conversation list.
- Composer stays pinned to the bottom.
- Timeline uses virtualized or incremental rendering once rooms get large.

Desktop behavior:

- Left sidebar for conversations.
- Main timeline area.
- Optional right-side info panel.

## Authentication

PIdP remains authoritative.

Worker flow:

1. Read bearer token or session-derived token.
2. Validate with `https://id.codecollective.us/auth/me`.
3. Map PIdP user ID to chat membership.
4. Authorize every conversation access.

Do not trust client-provided user IDs for membership or sender identity.

## Authorization Rules

- DM conversations require both caller and target to be active users.
- Organization rooms require membership, attendance, or admin role depending on room policy.
- Event rooms can allow attendees and organizers.
- Public read-only rooms can be added later, but should still protect writes.
- Moderators/admins can delete abusive messages.

## Attachments

Use R2 for files.

Flow:

1. Client asks for an upload URL.
2. Worker verifies auth and size/type policy.
3. Client uploads to R2.
4. Client commits attachment metadata.
5. Message references `attachment_id`.

Start with conservative limits:

- Images: 5 MB
- Files: 10 MB
- Allowed MIME types only
- Optional thumbnail generation later

## Cost Control

This can be effectively free for early Code Collective usage if we keep the initial implementation modest.

Free/low-cost practices:

- Start with REST + polling before WebSocket fanout if needed.
- Use D1 for message metadata and text.
- Use R2 only for attachments.
- Keep attachment size limits low.
- Use pagination everywhere.
- Avoid always-on servers.
- Avoid large public rooms until moderation and retention exist.
- Add retention policies for old attachments.

Cloudflare free tier limits can change, so this should be treated as “free for early scale,” not a contractual guarantee.

## Staged Rollout

### Phase 1: Durable Persistence, Polling

- D1 tables.
- REST endpoints for conversations and messages.
- Inbox button creates/opens DM conversations.
- Cursor sync with `afterSequence`.
- Adaptive polling every few seconds.
- Completed as the correctness and recovery path.

This is the simplest production-worthy version.

### Phase 2: Durable Object Realtime

- Completed for active room fanout with Cloudflare WebSocket Hibernation.
- Broadcast new messages, receipts, typing, and presence as best-effort acceleration.
- Keep HTTP send and `/sync` fallback as the correctness path.

### Phase 2B: SSE or Long-Poll Fallback

- Add one-way event stream endpoint if WebSocket reliability or cost is a concern.
- Keep sends over ordinary HTTP POST.
- Fall back to adaptive polling where SSE is unavailable.

### Phase 3: Attachments

- R2 upload flow.
- Image/file messages.
- Attachment retention policy.

### Phase 4: Notifications

- Queue-based push notification fanout.
- Email digest fallback.
- Mobile notification integration.

### Phase 5: Federation or Matrix Bridge

- Export messages.
- Bridge selected rooms to Matrix if federation becomes important.
- Optionally migrate `VITE_MATRIX_BASE_URL` to `matrix.codecollective.us`.

## Matrix Position

Matrix should remain a temporary/manual fallback while native Code Collective chat is built.

Current temporary setup:

- Frontend defaults to `https://matrix.org`.
- `VITE_MATRIX_BASE_URL` remains the migration switch.

Long term:

- Native Cloudflare chat should handle public profile inbox and community chat.
- Matrix can be added later as a bridge or interoperable backend if federation becomes a product requirement.

## Open Implementation Tasks

- Run the Selenium Docker two-robot chat smoke in CI or a scheduled live-test environment with robot credentials.
- Consider SSE or long-poll fallback before relying on WebSockets everywhere.
- Add native group/org room creation and membership policy endpoints.
- Add attachment upload and commit endpoints backed by R2.
- Keep Matrix manual connect path as fallback.
- Add tests for frontend optimistic retry behavior and adapter polling.
- Add live WebSocket-specific smoke coverage that verifies `message.created` arrives without waiting for polling.
- Add backend pagination edge-case tests around sequence gaps and deleted/hidden messages.

## Live Smoke Test

The native chat UI has a Selenium smoke test in `portal/web/scripts/selenium-chat-smoke.py` and a Docker wrapper in `portal/web/scripts/run-selenium-chat-smoke.sh`.

The smoke test:

1. Creates or reuses two PIdP robot accounts.
2. Enables public contact pages for both robots.
3. Starts `selenium/standalone-chrome` when using the Docker wrapper.
4. Logs each robot in through the portal UI in a separate browser session.
5. Opens a direct message with `/chat?start=dm&user=:slug`.
6. Sends a message from robot A to robot B.
7. Verifies robot B receives it in the UI.
8. Sends a reply from robot B to robot A.
9. Verifies robot A receives the reply in the UI.

Required environment variables:

- `CHAT_ROBOT_A_EMAIL`
- `CHAT_ROBOT_A_PASSWORD`
- `CHAT_ROBOT_B_EMAIL`
- `CHAT_ROBOT_B_PASSWORD`

For local development, store these in `portal/web/.env.selenium-chat`. That file is intentionally git-ignored and the Docker wrapper loads it automatically.

The live Code Collective smoke robots are pre-provisioned and their local test configuration is stored in `portal/web/.env.selenium-chat`. That file also enables `CHAT_ROBOTS_PREPROVISIONED=1` and points the test at the current live portal, PIdP, and org API origins.

For live smoke testing, PIdP exposes a guarded `POST /auth/smoke-token` endpoint. It requires the Cloudflare `SMOKE_TEST_SECRET` and only mints a normal session cookie for an already-active user. This exists to keep browser UI smoke tests reliable when ordinary credential auth is blocked by live edge protections; it is not a public registration or impersonation path.

Useful optional environment variables:

- `PORTAL_BASE_URL`, default `https://codecollective.us/p`
- `PIDP_BASE_URL`, default `https://id.codecollective.us`
- `ORG_API_BASE_URL`, default inferred as `https://codecollective.us/api/org`
- `CHAT_ROBOT_A_SLUG`, default `chat-robot-a`
- `CHAT_ROBOT_B_SLUG`, default `chat-robot-b`
- `SELENIUM_CHAT_SHOT_DIR`, default `/tmp/codecollective-chat-selenium`
- `CHAT_ROBOTS_PREPROVISIONED=1` to skip robot provisioning and use existing robot contact pages
- `CHAT_SMOKE_TEST_SECRET` to enable the guarded PIdP browser-session fallback for live smoke tests

Run with Docker:

```sh
cd portal/web
npm run test:chat:selenium:docker
```

Run against an already-running Selenium server:

```sh
cd portal/web
npm run test:chat:selenium
```

Latest live verification:

- Date: 2026-06-07.
- Command: `npm run test:chat:selenium:docker` from `portal/web`.
- Target: `https://codecollective.us/p`.
- Result: passed.
- Evidence: screenshots written under `/tmp/codecollective-chat-selenium-2def1bd3`.
- Verified flow: robot A logged in, robot B logged in, A opened a DM to B, B received A's message, B replied, and A received the reply.

Latest live WebSocket verification:

- Date: 2026-06-07.
- Target: `https://chat-codecollective.jcloiacon.workers.dev`.
- Result: passed.
- Verified flow: robot A opened an authenticated hibernating WebSocket with the `pidp.<base64url-token>` subprotocol, robot B sent through the HTTP message endpoint, and robot A received `message.created` over the WebSocket without waiting for polling.

## Completed Backend Preparation

- Created `portal/chat-worker/` as a separate Cloudflare Worker boundary.
- Created remote D1 database `chat`.
- Applied D1 migrations for conversations, members, messages, attachments, receipts, idempotency, and sequence sync.
- Deployed the worker to `https://chat-codecollective.jcloiacon.workers.dev`.
- Added hibernating Durable Object WebSocket fanout and protected HTTP routes.
- Added native portal chat page as the default `/chat` route with Matrix fallback by env flag.
- Added tests for auth, DM creation/reuse, message idempotency, sequence sync, message persistence/listing, and read receipts.
- Added Selenium Docker smoke-test tooling for two-account UI chat verification and verified it against the live deployment.
