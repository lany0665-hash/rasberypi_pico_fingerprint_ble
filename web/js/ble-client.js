import {
  CONTROL_UUID,
  encodeCommand,
  EVENT_UUID,
  SERVICE_UUID,
} from "./protocol.js";

const decoder = new TextDecoder("utf-8", { fatal: true });

export class BleClient extends EventTarget {
  constructor() {
    super();
    this.device = null;
    this.server = null;
    this.controlCharacteristic = null;
    this.eventCharacteristic = null;
    this._onDisconnected = this._onDisconnected.bind(this);
    this._onNotification = this._onNotification.bind(this);
  }

  static get supported() {
    return typeof navigator !== "undefined" && Boolean(navigator.bluetooth);
  }

  get connected() {
    return Boolean(this.device?.gatt?.connected && this.controlCharacteristic);
  }

  async connect() {
    if (!BleClient.supported) {
      throw new Error("이 브라우저는 Web Bluetooth를 지원하지 않습니다. HTTPS 또는 localhost의 Chrome/Edge를 사용하십시오.");
    }
    try {
      this.device = await navigator.bluetooth.requestDevice({
        filters: [{ services: [SERVICE_UUID] }],
        optionalServices: [SERVICE_UUID],
      });
      this.device.addEventListener("gattserverdisconnected", this._onDisconnected);
      this.server = await this.device.gatt.connect();
      const service = await this.server.getPrimaryService(SERVICE_UUID);
      this.controlCharacteristic = await service.getCharacteristic(CONTROL_UUID);
      this.eventCharacteristic = await service.getCharacteristic(EVENT_UUID);
      await this.eventCharacteristic.startNotifications();
      this.eventCharacteristic.addEventListener("characteristicvaluechanged", this._onNotification);
      this.dispatchEvent(new CustomEvent("connected", { detail: { name: this.device.name || "이름 없는 기기" } }));
    } catch (error) {
      const failedDevice = this.device;
      this._forgetConnection();
      if (failedDevice?.gatt?.connected) {
        failedDevice.gatt.disconnect();
      }
      throw this._friendlyError(error, "BLE 연결");
    }
  }

  async send(command) {
    if (!this.connected) {
      throw new Error("Pico W BLE 기기에 연결되어 있지 않습니다.");
    }
    const bytes = encodeCommand(command);
    try {
      if (this.controlCharacteristic.writeValueWithResponse) {
        await this.controlCharacteristic.writeValueWithResponse(bytes);
      } else {
        await this.controlCharacteristic.writeValue(bytes);
      }
    } catch (error) {
      throw this._friendlyError(error, "BLE 명령 전송");
    }
  }

  disconnect() {
    if (this.device?.gatt?.connected) {
      this.device.gatt.disconnect();
    } else {
      this._forgetConnection();
    }
  }

  _onNotification(event) {
    try {
      const bytes = new Uint8Array(
        event.target.value.buffer,
        event.target.value.byteOffset,
        event.target.value.byteLength,
      );
      const text = decoder.decode(bytes);
      const payload = JSON.parse(text);
      if (!payload || typeof payload !== "object" || Array.isArray(payload) || typeof payload.event !== "string") {
        throw new Error("event 필드가 없는 JSON입니다.");
      }
      this.dispatchEvent(new CustomEvent("notification", { detail: payload }));
    } catch (error) {
      this.dispatchEvent(new CustomEvent("malformed-notification", {
        detail: { message: `BLE 알림을 해석할 수 없습니다: ${error.message}` },
      }));
    }
  }

  _onDisconnected() {
    const name = this.device?.name || "Pico W";
    this._forgetConnection();
    this.dispatchEvent(new CustomEvent("disconnected", { detail: { name } }));
  }

  _forgetConnection() {
    if (this.eventCharacteristic) {
      this.eventCharacteristic.removeEventListener("characteristicvaluechanged", this._onNotification);
    }
    if (this.device) {
      this.device.removeEventListener("gattserverdisconnected", this._onDisconnected);
    }
    this.server = null;
    this.controlCharacteristic = null;
    this.eventCharacteristic = null;
  }

  _friendlyError(error, operation) {
    if (error?.name === "NotFoundError") {
      return new Error("기기 선택이 취소되었거나 요구한 Pico W 서비스를 찾지 못했습니다.");
    }
    if (error?.name === "SecurityError") {
      return new Error("Web Bluetooth는 HTTPS 또는 localhost와 사용자 버튼 동작이 필요합니다.");
    }
    return new Error(`${operation} 실패: ${error?.message || "알 수 없는 오류"}`);
  }
}
