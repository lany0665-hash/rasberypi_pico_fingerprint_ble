# Pico W 지문 센서 웹 앱

`web/`은 빌드 도구나 npm 의존성 없이 배포 가능한 정적 웹 앱입니다. Pico W
AS608 펌웨어의 실제 BLE GATT 서비스에 연결해 제어 명령을 보내고, 동일한
Firebase RTDB 스키마의 이벤트 이력을 조회하거나 개별 삭제합니다.

## 지원 환경과 실행

Web Bluetooth는 보안 컨텍스트에서만 작동합니다. 다음 중 하나로 페이지를
열어야 합니다.

- 개발: 저장소 루트에서 `python -m http.server 8080 -d web`를 실행하고
  Chromium 기반 데스크톱 브라우저에서 `http://localhost:8080`을 엽니다.
- 배포: 정적 호스팅(GitHub Pages, Firebase Hosting 등)에 `web/` 내용을
  올리고 **HTTPS** URL로 엽니다.

Chrome, Edge 등 Chromium 계열의 최근 데스크톱/Android 브라우저를
사용하십시오. 기기 선택은 페이지가 자동으로 열 수 없으며 **BLE 기기 연결**
버튼을 누르는 사용자 동작에서만 열립니다. Safari 및 iPhone/iPad 일반
브라우저의 Web Bluetooth는 지원 대상으로 가정하지 않습니다. 지원되지 않는
브라우저, HTTP 배포, 연결/쓰기 오류는 UI에 한국어 오류로 표시됩니다.

## BLE 사용 방법

Pico W의 전원을 켜고 센서 배선을 마친 뒤 다음 순서로 사용합니다.

1. **BLE 기기 연결**을 누르고 광고 이름 `PicoW-Fingerprint`를 선택합니다.
2. 상태 알림을 받은 뒤 **센서 인증**을 눌러 `VERIFY`를 성공시킵니다.
3. 등록하려면 0~999 ID를 입력하고 **등록 시작**을 누릅니다. 첫 손가락을
   올린 다음 **다음 스캔**을 누르고, 안내가 `wait_second`로 바뀌면 손가락을
   뗀 뒤 같은 손가락을 다시 올려 **다음 스캔**을 누릅니다.
4. 필요 시 지문 식별, 템플릿 개수, 템플릿 삭제, 등록 취소를 사용합니다.
   템플릿 삭제는 별도 확인 창을 요구합니다.

앱은 펌웨어 외의 BLE 명령을 만들지 않습니다.

| UI 동작 | 펌웨어 명령 |
|---|---|
| 상태 새로고침 | `STATUS` |
| 센서 인증 | `VERIFY` |
| 등록 시작 | `ENROLL <0..999>` |
| 다음 스캔 | `NEXT` |
| 등록 취소 | `CANCEL` |
| 지문 식별 | `IDENTIFY` |
| 템플릿 개수 | `COUNT` |
| 템플릿 삭제 | `DELETE <0..999>` |

사용 UUID는 펌웨어 `ble_service.py`와 동일합니다.

| 항목 | UUID |
|---|---|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |
| Control (Write) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| Event (Notify) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |

Event 알림은 `{ "event": "...", "state": "..." }` JSON입니다. 이 앱은
알림 JSON이 잘못된 경우 해당 내용을 화면에 오류로 보이고 연결을 성공으로
표시하지 않습니다. 펌웨어의 ID 범위와 상태 기계가 최종 권한이므로 앱의
버튼 비활성화만 보안 경계로 생각하면 안 됩니다.

## Firebase RTDB 이력

장치 펌웨어는 다음 위치에 이벤트만 기록하며 지문 이미지나 원시 템플릿은
전송하지 않습니다.

```text
/fingerprint_events/<device-id>/<event-id>
```

예시 레코드:

```json
{
  "event": "match",
  "state": "idle",
  "id": 12,
  "score": 87
}
```

웹 앱의 Firebase 영역에 아래 값을 입력하고 **Firebase 설정 적용**을 누른 뒤
**이력 새로고침**을 누르십시오.

| 값 | 용도 |
|---|---|
| RTDB URL | `https://<database>.firebaseio.com` 또는 `...firebasedatabase.app`의 루트 URL |
| 장치 ID | 펌웨어 `FIREBASE_DEVICE_ID`와 같은 값 |
| Firebase 사용자 ID 토큰 | 해당 경로의 읽기/삭제 권한을 가진 짧은 수명의 Firebase Authentication ID 토큰 |

값은 브라우저 저장소에 저장하지 않고 현재 페이지 메모리에만 유지됩니다.
반복 개발이 필요하면 `config.example.js`를 `config.js`로 복사해 값을 넣을 수
있지만, 이 파일은 Git에서 제외되며 신뢰할 수 있는 개인 개발 환경에서만
사용하십시오. Firebase 사용자 ID 토큰, 장치의 Wi-Fi 비밀번호, 장치용
Firebase 토큰, CA 인증서를 정적 사이트나 Git에 넣으면 안 됩니다.

이 앱은 Firebase SDK나 API 키를 사용하지 않고 RTDB REST `GET`/`DELETE`에
사용자 ID 토큰을 `auth` 매개변수로 전달합니다. 별도 Firebase 웹 인증을
구현한다면 Firebase Web API 키는 비밀이 아니지만, 반드시 Firebase Auth
사용자 세션과 제한적인 RTDB Rules를 함께 사용해야 합니다. 브라우저에
Admin SDK 서비스 계정, 데이터베이스 secret, 장치의 장기 쓰기 토큰을 넣지
마십시오.

RTDB Rules는 사용자/장치 역할별로 최소 권한을 부여하십시오. 예를 들어
Custom Claims를 사용하는 경우 운영자는 읽기/이력 삭제, 장치 토큰은 해당
장치 경로에 쓰기만 가능하도록 검증할 수 있습니다. 다음은 개념 예시이며
사용자 인증 흐름과 Custom Claims를 실제로 구성한 뒤에만 적용해야 합니다.

```json
{
  "rules": {
    "fingerprint_events": {
      "$deviceId": {
        ".read": "auth != null && auth.token.role === 'operator'",
        ".write": "auth != null && (auth.token.role === 'operator' || auth.token.device_id === $deviceId)"
      }
    }
  }
}
```

정적 웹 호스트와 RTDB 도메인이 다르면 Firebase의 허용된 CORS 원본에도 배포
HTTPS 원본을 추가하십시오. `*`로 모든 원본을 허용하지 마십시오. 권한 부족,
CORS 차단, 만료된 토큰, 응답 형식 오류는 이력 패널에 명확하게 표시됩니다.

## 장치 설정과의 차이

Pico W의 `secrets.py`는 Wi-Fi, 장치가 이벤트를 쓰는 Firebase 자격 증명, CA
인증서를 보관합니다. 이 웹 앱은 이를 읽거나 공유하지 않습니다. 웹 앱에는
별도의 사용자 인증 토큰과 읽기/삭제 권한이 필요합니다. Firebase Console
프로젝트만 생성한 상태로는 장치 업로드나 웹 이력 접근이 되지 않습니다. RTDB
인스턴스, 인증 공급자, 제한적 Rules, 필요 시 CORS를 모두 구성해야 합니다.
