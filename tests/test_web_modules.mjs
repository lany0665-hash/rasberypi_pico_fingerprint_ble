import assert from "node:assert/strict";
import test from "node:test";

import {
  buildEventsUrl,
  normalizeEvents,
  validateFirebaseConfig,
} from "../web/js/firebase-history.js";
import { commandFor, encodeCommand, parseTemplateId } from "../web/js/protocol.js";

const config = {
  databaseUrl: "https://example-default-rtdb.firebaseio.com/",
  deviceId: "pico-w-01",
  authToken: "short-lived-token",
};

test("BLE command generation enforces firmware template range", () => {
  assert.equal(commandFor("enroll", "12"), "ENROLL 12");
  assert.equal(commandFor("delete", "0"), "DELETE 0");
  assert.throws(() => parseTemplateId("1000"));
  assert.throws(() => parseTemplateId("-1"));
  assert.throws(() => encodeCommand("한글"));
});

test("Firebase URLs stay within emitted event schema", () => {
  assert.deepEqual(validateFirebaseConfig(config), {
    databaseUrl: "https://example-default-rtdb.firebaseio.com",
    deviceId: "pico-w-01",
    authToken: "short-lived-token",
  });
  assert.equal(
    buildEventsUrl(config, "123-0001"),
    "https://example-default-rtdb.firebaseio.com/fingerprint_events/pico-w-01/123-0001.json?auth=short-lived-token",
  );
});

test("Firebase event normalization sorts records and accepts empty history", () => {
  assert.deepEqual(normalizeEvents(null), []);
  const events = normalizeEvents({
    "10-0001": { event: "match", id: 12 },
    "20-0001": { event: "enroll_complete", id: 13 },
  });
  assert.equal(events[0].recordId, "20-0001");
  assert.equal(events[0].id, 13);
  assert.equal(events[1].event, "match");
});
