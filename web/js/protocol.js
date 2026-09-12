export const SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
export const CONTROL_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
export const EVENT_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";
export const TEMPLATE_ID_MIN = 0;
export const TEMPLATE_ID_MAX = 999;
export const MAX_COMMAND_BYTES = 64;

const encoder = new TextEncoder();

export function parseTemplateId(value) {
  const text = String(value).trim();
  if (!/^(0|[1-9]\d*)$/.test(text)) {
    throw new Error("템플릿 ID는 0부터 999까지의 정수여야 합니다.");
  }
  const id = Number(text);
  if (!Number.isSafeInteger(id) || id < TEMPLATE_ID_MIN || id > TEMPLATE_ID_MAX) {
    throw new Error("템플릿 ID는 0부터 999까지여야 합니다.");
  }
  return id;
}

export function encodeCommand(command) {
  const bytes = encoder.encode(command);
  if (bytes.length === 0 || bytes.length > MAX_COMMAND_BYTES) {
    throw new Error("BLE 명령은 비어 있지 않은 최대 64바이트 ASCII여야 합니다.");
  }
  for (const byte of bytes) {
    if (byte > 0x7f) {
      throw new Error("BLE 명령은 ASCII만 사용할 수 있습니다.");
    }
  }
  return bytes;
}

export function commandFor(action, id) {
  switch (action) {
    case "verify":
      return "VERIFY";
    case "status":
      return "STATUS";
    case "next":
      return "NEXT";
    case "cancel":
      return "CANCEL";
    case "identify":
      return "IDENTIFY";
    case "count":
      return "COUNT";
    case "enroll":
      return `ENROLL ${parseTemplateId(id)}`;
    case "delete":
      return `DELETE ${parseTemplateId(id)}`;
    default:
      throw new Error("지원하지 않는 Pico W 명령입니다.");
  }
}

export function enrollmentHint(state) {
  if (state === "wait_first") {
    return "첫 번째 손가락 스캔을 준비한 뒤 ‘다음 스캔’을 누르십시오.";
  }
  if (state === "wait_second") {
    return "손가락을 뗀 뒤 같은 손가락을 다시 올리고 ‘다음 스캔’을 누르십시오.";
  }
  return "센서 인증 후 등록할 템플릿 ID를 입력하십시오.";
}
