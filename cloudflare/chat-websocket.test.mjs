import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';

test('shared chat proxy preserves the WebSocket upgrade and authenticated protocol', async t => {
 const socket={fixture:'accepted-socket'};
 const upstream={status:101,webSocket:socket,headers:new Headers({'sec-websocket-protocol':'pidp.local-fixture'})};
 t.mock.method(globalThis,'fetch',async (url,init)=>{
  assert.equal(String(url),'https://chat.example/api/network/chat/conversations/local-room/socket');
  assert.equal(init.headers.get('upgrade'),'websocket');
  assert.equal(init.headers.get('sec-websocket-protocol'),'pidp.local-fixture');
  return upstream;
 });
 const response=await worker.fetch(new Request('https://codecollective.us/api/chat/api/network/chat/conversations/local-room/socket',{headers:{upgrade:'websocket','sec-websocket-protocol':'pidp.local-fixture'}}),{CHAT_API_ORIGIN:'https://chat.example'},{});
 assert.equal(response,upstream);assert.equal(response.webSocket,socket);
});
