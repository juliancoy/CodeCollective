import assert from "node:assert/strict";
import test from "node:test";

import worker, { canonicalPortalUrl } from "./portal-redirect.js";

test("maps the retired portal root to the canonical portal root", () => {
  assert.equal(
    canonicalPortalUrl("https://codecollective-portal.example/").toString(),
    "https://codecollective.us/p/",
  );
});

test("preserves paths and query strings", () => {
  assert.equal(
    canonicalPortalUrl("https://codecollective-portal.example/orgs/42?tab=events").toString(),
    "https://codecollective.us/p/orgs/42?tab=events",
  );
});

test("returns a permanent method-preserving redirect", async () => {
  const response = await worker.fetch(
    new Request("https://codecollective-portal.example/login?next=%2Forgs"),
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    "https://codecollective.us/p/login?next=%2Forgs",
  );
});
