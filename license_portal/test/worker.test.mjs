import assert from "node:assert/strict";
import test from "node:test";

import { __test } from "../src/worker.js";

test("license key generator creates keys accepted by the validator", () => {
  const key = __test.createLicenseKey();
  assert.match(key, /^CVOCR(?:-[A-Z2-9]{4}){5}$/);
  assert.equal(__test.normalizeLicenseKey(key.toLowerCase()), key);
  assert.equal(__test.normalizeLicenseKey("invalid"), "");
});

test("certificate canonical form stays stable across worker and desktop client", () => {
  const certificate = {
    check_after: "2026-08-25T00:00:00.000Z",
    device_hash: "device",
    expires_at: null,
    issued_at: "2026-08-18T00:00:00.000Z",
    license_id: "11111111-1111-4111-8111-111111111111",
    license_type: "perpetual",
    status: "active",
    v: 1,
  };
  assert.equal(
    __test.canonicalCertificate(certificate),
    '{"check_after":"2026-08-25T00:00:00.000Z","device_hash":"device","expires_at":null,"issued_at":"2026-08-18T00:00:00.000Z","license_id":"11111111-1111-4111-8111-111111111111","license_type":"perpetual","status":"active","v":1}'
  );
});

test("admin helpers reject malformed device and expiry input", () => {
  assert.equal(__test.normalizeDeviceId("abc"), "");
  assert.equal(__test.normalizeDeviceId("a".repeat(32)), "a".repeat(32));
  assert.equal(__test.normalizeExpiry("2020-01-01", "time"), null);
  assert.equal(__test.normalizeExpiry("", "perpetual"), null);
  assert.equal(__test.validUuid("11111111-1111-4111-8111-111111111111"), true);
  assert.equal(__test.timingSafeEqual("same", "same"), true);
  assert.equal(__test.timingSafeEqual("same", "other"), false);
});

test("portal responses apply baseline browser-hardening headers", () => {
  const headers = __test.securityHeaders();
  assert.equal(headers["Referrer-Policy"], "no-referrer");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.match(headers["Permissions-Policy"], /camera=/);
});
