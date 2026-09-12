# Pico W AS608 BLE 지문 등록

Raspberry Pi Pico W와 MicroPython으로 AS608 호환 UART 지문 센서를
Bluetooth Low Energy(BLE)로 제어하는 프로젝트입니다. 휴대폰에서 센서
인증, 2회 스캔 등록, 식별, 템플릿 삭제와 개수 조회를 할 수 있으며, 필요할
경우 이벤트를 Firebase Realtime Database(RTDB)에 전송합니다.

기본 설정은 **안전한 로컬 전용**입니다. Wi-Fi 또는 Firebase를 설정하지
않으면 센서와 BLE는 그대로 작동하고 네트워크 요청은 전혀 하지 않습니다.

## 준비물

- Raspberry Pi Pico W
- AS608 또는 프로토콜 호환 지문 센서
- 데이터 전송 가능한 USB 케이블과 [Thonny](https://thonny.org/)
- 최신 **Raspberry Pi Pico W용 MicroPython** 펌웨어. `machine`,
  `network`, `bluetooth`, `socket`, `ssl`, `ujson` 모듈이 포함되어야
  합니다. 최근의 공식 Pico W 펌웨어에는 일반적으로 포함됩니다.
  `bluetooth`가 필수이므로, Pico W가 아닌 보드용 펌웨어나 Bluetooth가
  빠진 오래된/최소 빌드에서는 이 BLE 서비스를 사용할 수 없습니다.
- 선택 사항: Firebase 프로젝트. `블루투스 지문등록` Firebase Console
  프로젝트만으로는 업로드할 수 없습니다. RTDB 인스턴스를 생성하고 장치에
  맞는 인증/접근 정책을 별도로 설정해야 합니다.

## 배선

기본 `config.py` 설정은 UART0, 57,600 baud입니다.

| Pico W | AS608 | 용도 |
|---|---|---|
| GP0 (UART0 TX) | 센서 RXD | Pico에서 센서로 보내는 직렬 데이터 |
| GP1 (UART0 RX) | 센서 TXD | 센서에서 Pico로 보내는 직렬 데이터 |
| GND | GND | **반드시 공통 접지** |
| 적절한 외부 전원 | VCC | 센서 전원 |

TX/RX는 표와 같이 반드시 교차 연결해야 합니다. 모든 AS608 보드의 전원
전압과 UART 논리 전압이 같다고 가정하면 안 되므로 해당 센서의 데이터시트를
먼저 확인하십시오. 피크 전류를 공급할 수 있는 전원을 쓰고 Pico와 접지를
공유하십시오. 센서 TX가 Pico W GPIO 허용치인 3.3 V를 넘을 수 있으면
레벨 시프터를 사용해야 합니다. 5 V UART TX를 Pico에 직접 연결하면 안 됩니다.

## Thonny 설치와 업로드

1. Pico W에 최신 MicroPython UF2를 설치합니다. Thonny에서
   **MicroPython (Raspberry Pi Pico)** 인터프리터와 올바른 COM 포트를
   선택합니다.
2. Thonny에서 이 저장소를 엽니다.
3. `secrets.example.py`를 새 로컬 파일 `secrets.py`로 복사합니다. 네트워크
   보고가 필요할 때만 본인의 값을 넣으십시오. `secrets.py`를 업로드 외의
   위치에 공유하거나 Git에 커밋하면 안 됩니다.
4. Pico 파일시스템 루트에 `main.py`, `config.py`, `as608.py`,
   `ble_service.py`, `wifi.py`, `firebase.py`와, 필요 시 `secrets.py`를
   업로드합니다.
5. `main.py`를 실행합니다. 재부팅 뒤에도 자동 실행하려면 장치의
   `main.py`로 두십시오. UART 핀, baud rate, 센서 주소/비밀번호와
   템플릿 ID 범위는 `config.py`에서만 변경합니다.

센서 공장 비밀번호는 흔히 `0x00000000`이지만 보장되지 않습니다. 변경된
센서라면 `config.py`의 `AS608_PASSWORD`를 맞추십시오. 템플릿을 사용하는
명령은 `VERIFY`가 성공한 뒤에만 허용됩니다.

## BLE GATT 프로토콜

Pico는 `PicoW-Fingerprint` 이름으로 광고하며 다음 사용자 정의 서비스를
제공합니다.

| 항목 | UUID | 속성 |
|---|---|---|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | — |
| Control | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | Write, Write Without Response |
| Event | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | Notify |

명령 전송 전에 Event 특성의 알림을 구독하십시오. Control 특성에 최대
64바이트의 ASCII 명령 하나를 씁니다. 명령은 대소문자를 구분하지 않습니다.

| 명령 | 결과 |
|---|---|
| `STATUS` | 현재 등록 상태와 센서 인증 상태를 알립니다. |
| `VERIFY` | 설정된 AS608 비밀번호를 확인합니다. |
| `ENROLL 12` | ID 12의 2회 스캔 등록을 시작합니다. 기본 범위는 `0`~`999`입니다. |
| `NEXT` | 첫 스캔 상태에서는 이미지를 캡처/변환합니다. 두 번째 상태에서는 다시 캡처/변환한 뒤 템플릿을 생성하고 저장합니다. 각 안내 이벤트 뒤 손가락을 올린 상태에서만 보내십시오. |
| `CANCEL` | 진행 중인 등록을 취소하고 idle 상태로 돌아갑니다. |
| `IDENTIFY` | 손가락을 캡처하여 저장된 템플릿에서 검색합니다. |
| `DELETE 12` | ID 12 템플릿을 삭제합니다. |
| `COUNT` | 저장된 템플릿 개수를 읽습니다. |

이벤트는 UTF-8 JSON 알림입니다. 예시는 다음과 같습니다.

```json
{"event":"enroll_started","state":"wait_first","id":12,"message":"Place finger for first scan, then send NEXT."}
{"event":"enroll_first_captured","state":"wait_second","id":12,"message":"Remove and place the same finger again, then send NEXT."}
{"event":"enroll_complete","state":"idle","id":12}
{"event":"match","state":"idle","id":12,"score":87}
{"event":"sensor_error","state":"wait_first","code":2,"message":"No finger detected"}
```

등록은 중앙 장치가 명시적으로 `NEXT`를 보낼 때만 다음 단계로 진행하며,
부분 등록을 저장하지 않습니다. 캡처가 실패하면 현재 등록 단계는 재시도할 수
있도록 유지됩니다. `CANCEL`, 잘못된 명령, 범위를 벗어난 ID, 잘못된 상태의
명령은 성공으로 위장하지 않고 오류 이벤트를 보냅니다. BLE 자체에는 인증이나
암호화가 없습니다. 실제 생체 정보를 다루는 배포에서는 신뢰된 환경에서만
사용하고, 페어링/본딩 또는 앱 수준의 권한 제어를 추가하십시오.

## Wi-Fi와 Firebase RTDB

`secrets.example.py`는 다음 설정을 제공합니다.

```python
WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"
FIREBASE_DATABASE_URL = "https://your-project-default-rtdb.firebaseio.com"
FIREBASE_AUTH_TOKEN = "a-device-authorized-token"
FIREBASE_DEVICE_ID = "pico-w-01"
FIREBASE_CA_CERTIFICATE = "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
```

Firebase 설정 절차는 다음과 같습니다.

1. `블루투스 지문등록`에서 **Realtime Database**를 생성하고 정확한 HTTPS
   데이터베이스 URL을 복사합니다. DB에 따라 `...firebaseio.com` 또는
   `...firebasedatabase.app` 주소일 수 있습니다.
2. 규칙과 장치 인증을 명시적으로 설정합니다. 이 프로젝트는
   `?auth=<token>`을 붙인 REST `PUT` 요청을 사용합니다. Firebase
   Authentication ID 토큰 또는 Firebase가 지원하는, 권한을 최소화한
   장치 자격 증명을 사용하십시오. 운영 RTDB 규칙을 전체 공개로 열거나
   장기 고권한 자격 증명을 펌웨어에 넣으면 안 됩니다.
3. Firebase 데이터베이스 호스트 인증서를 검증할 PEM 형식 CA 인증서(필요하면
   체인)를 `FIREBASE_CA_CERTIFICATE`에 입력합니다. 이 값이 없거나 현
   펌웨어가 인증서 검증을 지원하지 않으면, 토큰을 전송하지 않고
   `firebase_error`를 알립니다.
4. 값은 반드시 추적되지 않는 `secrets.py`에만 입력합니다.

Wi-Fi와 Firebase 값을 모두 제공하고 Wi-Fi 접속에 성공하면 이벤트 레코드는
다음 위치에 작성됩니다.

```text
/fingerprint_events/<FIREBASE_DEVICE_ID>/<event-id>.json
```

코드는 서드파티 HTTP 라이브러리 없이 MicroPython 내장 `socket`/`ssl`로
HTTPS를 사용합니다. Wi-Fi 연결 뒤 `ntptime`으로 UTC 시간을 동기화한 후
`CERT_REQUIRED`와 제공한 CA 인증서로 서버 인증서를 검증합니다. TLS 지원,
신뢰 루트 인증서, 또는 `ntptime`은 MicroPython 펌웨어 빌드에 따라 다를 수
있으므로 인증서 검증에 실패하면 Pico W 펌웨어를 업데이트하십시오. Firebase
설정 또는 네트워크 실패는 BLE `firebase_error` 이벤트로 알리고 성공으로
표시하지 않습니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 장치 시작 및 BLE, 센서, Wi-Fi, 보고 모듈 연결 |
| `config.py` | UART, AS608, BLE, Wi-Fi, Firebase 중앙 설정 |
| `as608.py` | 길이와 체크섬을 검증하는 AS608 패킷 드라이버 |
| `ble_service.py` | BLE GATT 서비스와 안전한 등록 상태 기계 |
| `wifi.py` | 명시적 Pico W Wi-Fi 연결 도우미 |
| `firebase.py` | 최소 HTTPS Firebase RTDB REST 이벤트 보고기 |
| `secrets.example.py` | 복사 전용 비밀 설정 템플릿 |
| `web/` | Web Bluetooth 제어 및 Firebase 이력 관리 정적 웹 앱 |

## 웹 제어 앱

`web/`에는 Pico W를 Web Bluetooth로 제어하고 Firebase 이벤트 이력을
관리하는 의존성 없는 브라우저 앱이 있습니다. 설치, 보안 설정, 지원 브라우저,
BLE 명령 매핑은 [`web/README.md`](web/README.md)를 참고하십시오.

## 제한 및 보안 주의

일반 AS608 명령 집합을 구현했지만 호환 센서마다 비밀번호, baud rate, 주소,
용량, 오류 코드가 다를 수 있습니다. 먼저 민감하지 않은 템플릿으로
시험하십시오. 이 프로젝트는 이미지나 원시 템플릿을 Firebase로 보내지 않고
작업 이벤트만 전송하지만, 템플릿 ID와 일치 활동도 생체 보안 정보이므로
접근 제어와 보존 정책이 필요합니다. 펌웨어 업데이트, 템플릿 다운로드, BLE
페어링, 안전한 토큰 갱신은 포함하지 않습니다.
