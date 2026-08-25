const textEncoder = new TextEncoder();
const CERTIFICATE_VERSION = 1;
const DEFAULT_OFFLINE_GRACE_DAYS = 7;
const SESSION_TTL_SECONDS = 12 * 60 * 60;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) {
      if (!env.ASSETS) return response({ error: "Trang quản trị chưa được build." }, 503);
      return secureAssetResponse(await env.ASSETS.fetch(request));
    }
    try {
      return await routeApi(request, env, url);
    } catch (error) {
      console.error("license_api_error", error instanceof Error ? error.message : "unknown");
      return response({ error: "Máy chủ bản quyền gặp lỗi tạm thời." }, 500);
    }
  },
};

async function routeApi(request, env, url) {
  if (request.method === "GET" && url.pathname === "/api/health") {
    return response({ ok: true, service: "checkvehicle-license" });
  }
  if (request.method === "POST" && url.pathname === "/api/activate") {
    return activateLicense(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/validate") {
    return validateLicense(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/admin/login") {
    return adminLogin(request, env, url);
  }
  if (request.method === "POST" && url.pathname === "/api/admin/logout") {
    return adminLogout(request, env, url);
  }
  if (!url.pathname.startsWith("/api/admin/")) {
    return response({ error: "Không tìm thấy API." }, 404);
  }
  const session = await requireAdmin(request, env, url);
  if (!session.ok) {
    return session.response;
  }
  if (request.method === "GET" && url.pathname === "/api/admin/licenses") {
    return listLicenses(env);
  }
  if (request.method === "POST" && url.pathname === "/api/admin/licenses") {
    return issueLicense(request, env);
  }
  const revokeMatch = url.pathname.match(/^\/api\/admin\/licenses\/([0-9a-f-]{36})\/revoke$/i);
  if (request.method === "POST" && revokeMatch) {
    return revokeLicense(env, revokeMatch[1]);
  }
  const resetMatch = url.pathname.match(/^\/api\/admin\/licenses\/([0-9a-f-]{36})\/reset-devices$/i);
  if (request.method === "POST" && resetMatch) {
    return resetActivations(env, resetMatch[1]);
  }
  return response({ error: "Không tìm thấy API quản trị." }, 404);
}

async function activateLicense(request, env) {
  const body = await readJson(request);
  const key = normalizeLicenseKey(body.key);
  const deviceId = normalizeDeviceId(body.deviceId);
  const deviceLabel = normalizeLabel(body.deviceLabel);
  if (!key || !deviceId) {
    return response({ error: "Nhập key bản quyền và mã thiết bị hợp lệ." }, 400);
  }
  const rate = await consumeRateLimit(env, `activate:${await anonymizedIp(request, env)}`, 8, 15 * 60);
  if (!rate.allowed) {
    return response({ error: "Đã thử quá nhiều lần. Hãy chờ ít phút rồi thử lại." }, 429);
  }
  const keyHmac = await hmacBase64Url(env.LICENSE_KEY_PEPPER, key);
  const license = await env.DB.prepare(
    "SELECT id, license_type, status, expires_at, max_devices FROM licenses WHERE key_hmac = ?"
  ).bind(keyHmac).first();
  if (!license) {
    return response({ error: "Key bản quyền không hợp lệ." }, 401);
  }
  return activateForLicense(env, license, deviceId, deviceLabel, "activated");
}

async function validateLicense(request, env) {
  const body = await readJson(request);
  const licenseId = validUuid(body.licenseId) ? body.licenseId : "";
  const deviceId = normalizeDeviceId(body.deviceId);
  if (!licenseId || !deviceId) {
    return response({ error: "Dữ liệu kiểm tra bản quyền không hợp lệ." }, 400);
  }
  const license = await env.DB.prepare(
    "SELECT id, license_type, status, expires_at, max_devices FROM licenses WHERE id = ?"
  ).bind(licenseId).first();
  if (!license) {
    return response({ error: "Không tìm thấy key bản quyền." }, 404);
  }
  return activateForLicense(env, license, deviceId, "", "validated", false);
}

async function activateForLicense(env, license, deviceId, deviceLabel, eventType, allowNewDevice = true) {
  const now = new Date();
  const state = licenseState(license, now);
  if (state !== "active") {
    return response({ error: licenseStateMessage(state) }, 403);
  }
  const deviceHmac = await hmacBase64Url(env.LICENSE_KEY_PEPPER, `device:${deviceId}`);
  let activation = await env.DB.prepare(
    "SELECT id, revoked_at FROM activations WHERE license_id = ? AND device_hmac = ?"
  ).bind(license.id, deviceHmac).first();
  if (activation?.revoked_at) {
    return response({ error: "Thiết bị này đã bị quản trị viên thu hồi." }, 403);
  }
  if (!activation && !allowNewDevice) {
    return response({ error: "Thiết bị chưa được kích hoạt cho key này." }, 403);
  }
  if (!activation) {
    const count = await env.DB.prepare(
      "SELECT COUNT(*) AS total FROM activations WHERE license_id = ? AND revoked_at IS NULL"
    ).bind(license.id).first();
    if (Number(count?.total || 0) >= Number(license.max_devices || 1)) {
      return response({ error: "Key này đã đạt số thiết bị được phép. Liên hệ quản trị viên để đặt lại thiết bị." }, 409);
    }
    const activationId = crypto.randomUUID();
    await env.DB.prepare(
      "INSERT INTO activations (id, license_id, device_hmac, device_label, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)"
    ).bind(activationId, license.id, deviceHmac, deviceLabel, now.toISOString(), now.toISOString()).run();
    activation = { id: activationId };
    await addEvent(env, license.id, eventType, deviceLabel ? `Thiết bị: ${deviceLabel}` : "Thiết bị mới");
  } else {
    await env.DB.prepare("UPDATE activations SET last_seen_at = ? WHERE id = ?").bind(now.toISOString(), activation.id).run();
    await addEvent(env, license.id, eventType, "Gia hạn xác thực thiết bị");
  }
  const signed = await createSignedCertificate(env, license, deviceId, now);
  return response({ ok: true, license: publicLicense(license), certificate: signed.certificate, signature: signed.signature });
}

async function adminLogin(request, env, url) {
  if (!isSameOrigin(request, url)) {
    return response({ error: "Nguồn yêu cầu không hợp lệ." }, 403);
  }
  const body = await readJson(request);
  const code = String(body.code || "").trim();
  if (!code || code.length > 256) {
    return response({ error: "Nhập mã quản trị." }, 400);
  }
  const rate = await consumeRateLimit(env, `admin:${await anonymizedIp(request, env)}`, 5, 15 * 60);
  if (!rate.allowed) {
    return response({ error: "Đã thử quá nhiều lần. Hãy chờ ít phút rồi đăng nhập lại." }, 429);
  }
  const suppliedHash = await sha256Base64Url(code);
  if (!timingSafeEqual(suppliedHash, String(env.ADMIN_CODE_SHA256 || ""))) {
    return response({ error: "Mã quản trị không đúng." }, 401);
  }
  const token = await signSession(env, { exp: epochSeconds() + SESSION_TTL_SECONDS, scope: "license-admin" });
  return response(
    { ok: true },
    200,
    { "Set-Cookie": `checkvehicle_admin=${token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=${SESSION_TTL_SECONDS}` }
  );
}

async function adminLogout(request, env, url) {
  const session = await requireAdmin(request, env, url);
  if (!session.ok) {
    return session.response;
  }
  return response({ ok: true }, 200, { "Set-Cookie": "checkvehicle_admin=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0" });
}

async function requireAdmin(request, env, url) {
  if (!isSameOrigin(request, url)) {
    return { ok: false, response: response({ error: "Nguồn yêu cầu không hợp lệ." }, 403) };
  }
  const token = readCookie(request.headers.get("Cookie"), "checkvehicle_admin");
  const payload = token ? await verifySession(env, token) : null;
  if (!payload || payload.scope !== "license-admin" || Number(payload.exp || 0) < epochSeconds()) {
    return { ok: false, response: response({ error: "Phiên quản trị đã hết hạn." }, 401) };
  }
  return { ok: true, payload };
}

async function listLicenses(env) {
  const result = await env.DB.prepare(
    `SELECT l.id, l.license_type, l.status, l.expires_at, l.max_devices, l.note, l.created_at, l.revoked_at,
      COUNT(a.id) FILTER (WHERE a.revoked_at IS NULL) AS active_devices
      FROM licenses l LEFT JOIN activations a ON a.license_id = l.id
      GROUP BY l.id ORDER BY l.created_at DESC LIMIT 250`
  ).all();
  return response({ licenses: (result.results || []).map((item) => ({ ...item, active_devices: Number(item.active_devices || 0) })) });
}

async function issueLicense(request, env) {
  const body = await readJson(request);
  const licenseType = body.licenseType === "perpetual" ? "perpetual" : "time";
  const expiresAt = normalizeExpiry(body.expiresAt, licenseType);
  const maxDevices = Math.max(1, Math.min(10, Number.parseInt(body.maxDevices, 10) || 1));
  const note = String(body.note || "").trim().slice(0, 240);
  if (licenseType === "time" && !expiresAt) {
    return response({ error: "Key có thời hạn cần ngày hết hạn hợp lệ." }, 400);
  }
  const key = createLicenseKey();
  const now = new Date().toISOString();
  const id = crypto.randomUUID();
  await env.DB.prepare(
    "INSERT INTO licenses (id, key_hmac, license_type, status, expires_at, max_devices, note, created_at) VALUES (?, ?, ?, 'active', ?, ?, ?, ?)"
  ).bind(id, await hmacBase64Url(env.LICENSE_KEY_PEPPER, key), licenseType, expiresAt, maxDevices, note, now).run();
  await addEvent(env, id, "issued", licenseType === "perpetual" ? "Key vĩnh viễn" : `Hết hạn ${expiresAt}`);
  return response({ ok: true, key, license: { id, license_type: licenseType, status: "active", expires_at: expiresAt, max_devices: maxDevices, note, created_at: now, active_devices: 0 } }, 201);
}

async function revokeLicense(env, licenseId) {
  const license = await env.DB.prepare("SELECT id, status FROM licenses WHERE id = ?").bind(licenseId).first();
  if (!license) {
    return response({ error: "Không tìm thấy key." }, 404);
  }
  if (license.status !== "revoked") {
    const now = new Date().toISOString();
    await env.DB.prepare("UPDATE licenses SET status = 'revoked', revoked_at = ? WHERE id = ?").bind(now, licenseId).run();
    await addEvent(env, licenseId, "revoked", "Quản trị viên thu hồi key");
  }
  return response({ ok: true });
}

async function resetActivations(env, licenseId) {
  const license = await env.DB.prepare("SELECT id FROM licenses WHERE id = ?").bind(licenseId).first();
  if (!license) {
    return response({ error: "Không tìm thấy key." }, 404);
  }
  const now = new Date().toISOString();
  await env.DB.prepare("UPDATE activations SET revoked_at = ? WHERE license_id = ? AND revoked_at IS NULL").bind(now, licenseId).run();
  await addEvent(env, licenseId, "devices_reset", "Đặt lại toàn bộ thiết bị");
  return response({ ok: true });
}

async function createSignedCertificate(env, license, deviceId, now) {
  const graceDays = Math.max(1, Math.min(30, Number.parseInt(env.OFFLINE_GRACE_DAYS, 10) || DEFAULT_OFFLINE_GRACE_DAYS));
  const certificate = {
    check_after: new Date(now.getTime() + graceDays * 24 * 60 * 60 * 1000).toISOString(),
    device_hash: await sha256Base64Url(deviceId),
    expires_at: license.expires_at || null,
    issued_at: now.toISOString(),
    license_id: license.id,
    license_type: license.license_type,
    status: "active",
    v: CERTIFICATE_VERSION,
  };
  const privateKey = await crypto.subtle.importKey(
    "pkcs8",
    base64UrlToBytes(env.LICENSE_SIGNING_PRIVATE_KEY_B64),
    { name: "Ed25519" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("Ed25519", privateKey, textEncoder.encode(canonicalCertificate(certificate)));
  return { certificate, signature: bytesToBase64Url(signature) };
}

function canonicalCertificate(certificate) {
  return JSON.stringify({
    check_after: certificate.check_after,
    device_hash: certificate.device_hash,
    expires_at: certificate.expires_at,
    issued_at: certificate.issued_at,
    license_id: certificate.license_id,
    license_type: certificate.license_type,
    status: certificate.status,
    v: certificate.v,
  });
}

function licenseState(license, now) {
  if (license.status !== "active") {
    return "revoked";
  }
  if (license.license_type === "time" && (!license.expires_at || new Date(license.expires_at).getTime() <= now.getTime())) {
    return "expired";
  }
  return "active";
}

function licenseStateMessage(state) {
  if (state === "expired") return "Key bản quyền đã hết hạn.";
  if (state === "revoked") return "Key bản quyền đã bị thu hồi.";
  return "Key bản quyền không dùng được.";
}

function publicLicense(license) {
  return { id: license.id, licenseType: license.license_type, expiresAt: license.expires_at || null, maxDevices: Number(license.max_devices || 1) };
}

function createLicenseKey() {
  const alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const bytes = new Uint8Array(20);
  crypto.getRandomValues(bytes);
  const value = [...bytes].map((item) => alphabet[item % alphabet.length]).join("");
  return `CVOCR-${value.match(/.{1,4}/g).join("-")}`;
}

function normalizeLicenseKey(value) {
  const key = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
  return /^CVOCR(?:-[A-Z2-9]{4}){5}$/.test(key) ? key : "";
}

function normalizeDeviceId(value) {
  const deviceId = String(value || "").trim();
  return /^[a-zA-Z0-9_-]{16,128}$/.test(deviceId) ? deviceId : "";
}

function normalizeLabel(value) {
  return String(value || "").replace(/[\r\n\t]/g, " ").trim().slice(0, 80);
}

function normalizeExpiry(value, licenseType) {
  if (licenseType === "perpetual") return null;
  const parsed = new Date(`${String(value || "").trim()}T23:59:59.999Z`);
  return Number.isFinite(parsed.getTime()) && parsed.getTime() > Date.now() ? parsed.toISOString() : null;
}

function validUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

async function addEvent(env, licenseId, eventType, eventNote) {
  await env.DB.prepare("INSERT INTO license_events (id, license_id, event_type, event_note, created_at) VALUES (?, ?, ?, ?, ?)")
    .bind(crypto.randomUUID(), licenseId, eventType, eventNote, new Date().toISOString()).run();
}

async function consumeRateLimit(env, scope, maxAttempts, windowSeconds) {
  const now = epochSeconds();
  const current = await env.DB.prepare("SELECT window_started_at, attempt_count, blocked_until FROM rate_limits WHERE scope = ?").bind(scope).first();
  if (current && Number(current.blocked_until || 0) > now) return { allowed: false };
  const withinWindow = current && now - Number(current.window_started_at) < windowSeconds;
  const attempts = withinWindow ? Number(current.attempt_count) + 1 : 1;
  const blockedUntil = attempts > maxAttempts ? now + windowSeconds : 0;
  await env.DB.prepare(
    "INSERT INTO rate_limits (scope, window_started_at, attempt_count, blocked_until) VALUES (?, ?, ?, ?) ON CONFLICT(scope) DO UPDATE SET window_started_at = excluded.window_started_at, attempt_count = excluded.attempt_count, blocked_until = excluded.blocked_until"
  ).bind(scope, withinWindow ? Number(current.window_started_at) : now, attempts, blockedUntil).run();
  return { allowed: attempts <= maxAttempts };
}

async function anonymizedIp(request, env) {
  return hmacBase64Url(env.LICENSE_KEY_PEPPER, `ip:${request.headers.get("CF-Connecting-IP") || "unknown"}`);
}

async function hmacBase64Url(secret, value) {
  const key = await crypto.subtle.importKey("raw", textEncoder.encode(String(secret || "")), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return bytesToBase64Url(await crypto.subtle.sign("HMAC", key, textEncoder.encode(value)));
}

async function sha256Base64Url(value) {
  return bytesToBase64Url(await crypto.subtle.digest("SHA-256", textEncoder.encode(value)));
}

async function signSession(env, payload) {
  const encoded = bytesToBase64Url(textEncoder.encode(JSON.stringify(payload)));
  return `${encoded}.${await hmacBase64Url(env.ADMIN_SESSION_SECRET, encoded)}`;
}

async function verifySession(env, token) {
  const [encoded, signature] = String(token || "").split(".");
  if (!encoded || !signature || !timingSafeEqual(signature, await hmacBase64Url(env.ADMIN_SESSION_SECRET, encoded))) return null;
  try {
    return JSON.parse(new TextDecoder().decode(base64UrlToBytes(encoded)));
  } catch {
    return null;
  }
}

function readCookie(header, name) {
  for (const pair of String(header || "").split(";")) {
    const [key, ...parts] = pair.trim().split("=");
    if (key === name) return parts.join("=");
  }
  return "";
}

function timingSafeEqual(left, right) {
  const leftBytes = textEncoder.encode(String(left || ""));
  const rightBytes = textEncoder.encode(String(right || ""));
  const length = Math.max(leftBytes.length, rightBytes.length);
  let difference = leftBytes.length ^ rightBytes.length;
  for (let index = 0; index < length; index += 1) difference |= (leftBytes[index] || 0) ^ (rightBytes[index] || 0);
  return difference === 0;
}

function isSameOrigin(request, url) {
  const origin = request.headers.get("Origin");
  return !origin || origin === url.origin;
}

function response(payload, status = 200, headers = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      ...securityHeaders(),
      ...headers,
    },
  });
}

function secureAssetResponse(asset) {
  const headers = new Headers(asset.headers);
  for (const [name, value] of Object.entries(securityHeaders())) headers.set(name, value);
  return new Response(asset.body, { status: asset.status, statusText: asset.statusText, headers });
}

function securityHeaders() {
  return {
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
  };
}

async function readJson(request) {
  try {
    const body = await request.json();
    return body && typeof body === "object" ? body : {};
  } catch {
    return {};
  }
}

function bytesToBase64Url(value) {
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  let binary = "";
  for (const item of bytes) binary += String.fromCharCode(item);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlToBytes(value) {
  const padded = String(value || "").replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(String(value || "").length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (item) => item.charCodeAt(0));
}

function epochSeconds() {
  return Math.floor(Date.now() / 1000);
}

export const __test = { canonicalCertificate, createLicenseKey, normalizeLicenseKey, normalizeDeviceId, normalizeExpiry, securityHeaders, timingSafeEqual, validUuid };
