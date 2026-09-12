function assertFirebaseKey(value, label) {
  const text = String(value || "").trim();
  if (!text || /[.#$[\]/]/.test(text)) {
    throw new Error(`${label}에 Firebase 경로에서 사용할 수 없는 문자가 있습니다.`);
  }
  return text;
}

export function validateFirebaseConfig(config) {
  const databaseUrl = String(config.databaseUrl || "").trim().replace(/\/+$/, "");
  let parsed;
  try {
    parsed = new URL(databaseUrl);
  } catch {
    throw new Error("Firebase RTDB URL 형식이 올바르지 않습니다.");
  }
  if (parsed.protocol !== "https:" || parsed.pathname !== "/") {
    throw new Error("Firebase RTDB URL은 경로 없는 https:// 호스트 주소여야 합니다.");
  }
  const deviceId = assertFirebaseKey(config.deviceId, "장치 ID");
  const authToken = String(config.authToken || "").trim();
  if (!authToken) {
    throw new Error("Firebase 사용자 ID 토큰을 입력하십시오.");
  }
  return { databaseUrl, deviceId, authToken };
}

export function buildEventsUrl(config, eventId = null) {
  const safe = validateFirebaseConfig(config);
  const suffix = eventId === null ? "" : `/${encodeURIComponent(assertFirebaseKey(eventId, "이벤트 ID"))}`;
  return `${safe.databaseUrl}/fingerprint_events/${encodeURIComponent(safe.deviceId)}${suffix}.json?auth=${encodeURIComponent(safe.authToken)}`;
}

export function normalizeEvents(payload) {
  if (payload === null) {
    return [];
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Firebase 이벤트 응답이 예상한 객체 형식이 아닙니다.");
  }
  return Object.entries(payload)
    .filter(([, event]) => event && typeof event === "object" && !Array.isArray(event))
    .map(([recordId, event]) => ({ recordId, ...event }))
    .sort((left, right) => right.recordId.localeCompare(left.recordId, undefined, { numeric: true }));
}

async function parseResponse(response) {
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`Firebase 요청 실패 (${response.status}): ${body.slice(0, 180) || response.statusText}`);
  }
  if (!body) {
    return null;
  }
  try {
    return JSON.parse(body);
  } catch {
    throw new Error("Firebase 응답이 유효한 JSON이 아닙니다.");
  }
}

export class FirebaseHistory {
  constructor(config) {
    this.config = validateFirebaseConfig(config);
  }

  async load() {
    try {
      const response = await fetch(buildEventsUrl(this.config), { headers: { Accept: "application/json" } });
      return normalizeEvents(await parseResponse(response));
    } catch (error) {
      throw new Error(`Firebase 이력 조회 실패: ${error.message}`);
    }
  }

  async delete(eventId) {
    try {
      const response = await fetch(buildEventsUrl(this.config, eventId), { method: "DELETE" });
      await parseResponse(response);
    } catch (error) {
      throw new Error(`Firebase 이력 삭제 실패: ${error.message}`);
    }
  }
}
