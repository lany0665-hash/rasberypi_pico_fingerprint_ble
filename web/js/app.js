import { BleClient } from "./ble-client.js";
import { FirebaseHistory } from "./firebase-history.js";
import { commandFor, enrollmentHint } from "./protocol.js";

const $ = (id) => document.getElementById(id);
const controls = ["status", "verify", "enroll", "next", "cancel", "identify", "count", "delete"];
const appConfig = window.PICO_APP_CONFIG?.firebase || {};

const ble = new BleClient();
let enrollmentState = "unknown";
let verified = false;
let historyClient = null;
let historyEvents = [];

function setStatus(message, kind = "neutral") {
  const status = $("global-status");
  status.textContent = message;
  status.className = `status status-${kind}`;
}

function setHistoryStatus(message, kind = "neutral") {
  const status = $("history-status");
  status.textContent = message;
  status.className = `status status-${kind}`;
}

function updateControls() {
  const connected = ble.connected;
  $("connect-button").disabled = connected || !BleClient.supported;
  $("disconnect-button").disabled = !connected;
  controls.forEach((name) => { $(`${name}-button`).disabled = !connected; });
  $("enroll-button").disabled = !connected || !verified || enrollmentState !== "idle";
  $("next-button").disabled = !connected || !verified || !["wait_first", "wait_second"].includes(enrollmentState);
  $("cancel-button").disabled = !connected || !["wait_first", "wait_second"].includes(enrollmentState);
  $("identify-button").disabled = !connected || !verified || enrollmentState !== "idle";
  $("count-button").disabled = !connected || !verified || enrollmentState !== "idle";
  $("delete-button").disabled = !connected || !verified || enrollmentState !== "idle";
  $("ble-state").textContent = connected ? "연결됨" : "연결 안 됨";
  $("ble-state").classList.toggle("connected", connected);
  $("enrollment-help").textContent = enrollmentHint(enrollmentState);
}

function renderConnection() {
  $("device-name").textContent = ble.connected ? (ble.device.name || "이름 없는 기기") : "선택되지 않음";
  $("enrollment-state").textContent = enrollmentState === "unknown" ? "알 수 없음" : enrollmentState;
  $("verification-state").textContent = verified ? "인증됨" : "확인 전";
  updateControls();
}

function addEvent(payload) {
  const list = $("event-list");
  const item = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = payload.event || "알 수 없는 이벤트";
  const detail = document.createElement("pre");
  detail.textContent = JSON.stringify(payload, null, 2);
  item.append(title, detail);
  list.prepend(item);
  while (list.children.length > 100) {
    list.lastElementChild.remove();
  }
  $("event-empty").hidden = true;
}

async function send(action, id) {
  try {
    await ble.send(commandFor(action, id));
    setStatus(`명령 전송: ${commandFor(action, id)}`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function selectedTemplateId(inputId) {
  return $(inputId).value;
}

function applyFirebaseConfig() {
  try {
    historyClient = new FirebaseHistory({
      databaseUrl: $("firebase-url").value,
      deviceId: $("firebase-device-id").value,
      authToken: $("firebase-token").value,
    });
    $("refresh-history-button").disabled = false;
    setHistoryStatus("Firebase 설정이 적용되었습니다. 이력 새로고침을 누르십시오.", "success");
  } catch (error) {
    historyClient = null;
    $("refresh-history-button").disabled = true;
    setHistoryStatus(error.message, "error");
  }
}

function eventText(event) {
  return Object.values(event).join(" ").toLowerCase();
}

function renderHistory() {
  const eventFilter = $("history-event-filter").value;
  const textFilter = $("history-text-filter").value.trim().toLowerCase();
  const visible = historyEvents.filter((event) =>
    (!eventFilter || event.event === eventFilter) &&
    (!textFilter || eventText(event).includes(textFilter)),
  );
  const body = $("history-body");
  body.replaceChildren();
  for (const event of visible) {
    const row = document.createElement("tr");
    const idCell = document.createElement("td");
    idCell.textContent = event.recordId;
    const eventCell = document.createElement("td");
    eventCell.textContent = event.event || "알 수 없음";
    const detailCell = document.createElement("td");
    detailCell.textContent = [
      event.state ? `상태: ${event.state}` : "",
      event.id !== undefined ? `템플릿 ID: ${event.id}` : "",
      event.score !== undefined ? `점수: ${event.score}` : "",
      event.count !== undefined ? `개수: ${event.count}` : "",
      event.message || "",
    ].filter(Boolean).join("\n") || JSON.stringify(event);
    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.className = "danger-outline";
    button.type = "button";
    button.textContent = "이력 삭제";
    button.addEventListener("click", () => deleteHistoryEvent(event.recordId));
    actionCell.append(button);
    row.append(idCell, eventCell, detailCell, actionCell);
    body.append(row);
  }
  $("history-empty").hidden = visible.length > 0;
}

async function refreshHistory() {
  if (!historyClient) {
    setHistoryStatus("먼저 Firebase 설정을 적용하십시오.", "error");
    return;
  }
  $("refresh-history-button").disabled = true;
  setHistoryStatus("Firebase 이력을 불러오는 중입니다.");
  try {
    historyEvents = await historyClient.load();
    renderHistory();
    setHistoryStatus(`${historyEvents.length}개의 이력을 불러왔습니다.`, "success");
  } catch (error) {
    setHistoryStatus(error.message, "error");
  } finally {
    $("refresh-history-button").disabled = false;
  }
}

async function deleteHistoryEvent(eventId) {
  if (!historyClient) {
    return;
  }
  if (!window.confirm(`Firebase 이력 "${eventId}"를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) {
    return;
  }
  try {
    await historyClient.delete(eventId);
    historyEvents = historyEvents.filter((event) => event.recordId !== eventId);
    renderHistory();
    setHistoryStatus(`이력 ${eventId}를 삭제했습니다.`, "success");
  } catch (error) {
    setHistoryStatus(error.message, "error");
  }
}

ble.addEventListener("connected", async (event) => {
  enrollmentState = "unknown";
  verified = false;
  renderConnection();
  setStatus(`${event.detail.name}에 연결되었습니다. 상태를 확인합니다.`, "success");
  await send("status");
});
ble.addEventListener("disconnected", () => {
  enrollmentState = "unknown";
  verified = false;
  renderConnection();
  setStatus("Pico W BLE 연결이 해제되었습니다.", "neutral");
});
ble.addEventListener("notification", (event) => {
  const payload = event.detail;
  if (typeof payload.state === "string") {
    enrollmentState = payload.state;
  }
  if (typeof payload.verified === "boolean") {
    verified = payload.verified;
  }
  if (payload.event === "verified") {
    verified = true;
  }
  addEvent(payload);
  renderConnection();
  setStatus(`Pico W 이벤트: ${payload.event}`, payload.event.includes("error") ? "error" : "success");
});
ble.addEventListener("malformed-notification", (event) => setStatus(event.detail.message, "error"));

$("connect-button").addEventListener("click", async () => {
  try {
    await ble.connect();
  } catch (error) {
    setStatus(error.message, "error");
    renderConnection();
  }
});
$("disconnect-button").addEventListener("click", () => ble.disconnect());
$("status-button").addEventListener("click", () => send("status"));
$("verify-button").addEventListener("click", () => send("verify"));
$("enroll-button").addEventListener("click", () => send("enroll", selectedTemplateId("enroll-id")));
$("next-button").addEventListener("click", () => send("next"));
$("cancel-button").addEventListener("click", () => send("cancel"));
$("identify-button").addEventListener("click", () => send("identify"));
$("count-button").addEventListener("click", () => send("count"));
$("delete-button").addEventListener("click", () => {
  const id = selectedTemplateId("delete-id");
  try {
    const command = commandFor("delete", id);
    if (window.confirm(`센서에서 템플릿 ID ${id}를 삭제하시겠습니까?`)) {
      send("delete", id);
    }
  } catch (error) {
    setStatus(error.message, "error");
  }
});
$("clear-events-button").addEventListener("click", () => {
  $("event-list").replaceChildren();
  $("event-empty").hidden = false;
});
$("apply-firebase-button").addEventListener("click", applyFirebaseConfig);
$("refresh-history-button").addEventListener("click", refreshHistory);
$("history-event-filter").addEventListener("change", renderHistory);
$("history-text-filter").addEventListener("input", renderHistory);

$("firebase-url").value = appConfig.databaseUrl || "";
$("firebase-device-id").value = appConfig.deviceId || "pico-w-01";
$("firebase-token").value = appConfig.authToken || "";
if (BleClient.supported) {
  $("bluetooth-support").textContent = "이 브라우저는 Web Bluetooth API를 감지했습니다.";
} else {
  $("bluetooth-support").textContent = "이 브라우저에서는 Web Bluetooth를 사용할 수 없습니다. HTTPS 또는 localhost의 Chrome/Edge 데스크톱을 사용하십시오.";
  setStatus("Web Bluetooth를 지원하지 않는 브라우저입니다.", "error");
}
renderConnection();
