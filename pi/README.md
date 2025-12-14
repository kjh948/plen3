# PLEN3 NanoPi Controller

이 프로젝트는 PLEN 로봇의 ESP8266 펌웨어 로직을 Armbian이 설치된 NanoPi Duo로 이식한 파이썬 컨트롤러입니다. PCA9685 PWM 드라이버를 사용하여 서보 모터를 제어하며, 기존 펌웨어의 모션 파일(`.json`)을 로드하여 재생할 수 있습니다.

## 설치 방법 (Installation)

1.  **필수 패키지 설치**:
    Armbian 환경에서 I2C 사용을 위한 시스템 패키지를 설치합니다.
    ```bash
    sudo apt-get update
    sudo apt-get install python3-pip python3-smbus i2c-tools
    ```

2.  **I2C 활성화**:
    `armbian-config` 등을 통해 I2C 버스가 활성화되어 있는지 확인하세요.
    ```bash
    i2cdetect -y 0
    # 또는
    i2cdetect -y 1
    ```
    (PCA9685의 기본 주소인 `0x40`이 보여야 합니다.)

3.  **Python 라이브러리 설치**:
    `pi` 디렉토리로 이동하여 의존성을 설치합니다.
    ```bash
    cd /home/pi/workspace/plen3/pi  # 실제 경로에 맞게 수정
    pip3 install -r requirements.txt
    ```

## 사용 방법 (Usage)

### 대화형 모드 실행
스크립트를 실행하면 사용 가능한 모션 파일 목록이 표시되며, 번호를 입력하여 실행할 수 있습니다.
```bash
python3 run.py
```

### 특정 모션 파일 실행
인자로 모션 파일 경로를 직접 지정하여 실행할 수도 있습니다.
```bash
python3 run.py /path/to/firmware/data/00_LStep.json
```

## 모터 채널 매핑 (Motor Channel Mapping)

PCA9685의 16개 채널(0 ~ 15)에 연결된 모터는 다음과 같습니다.
기존 펌웨어에서 GPIO로 제어하던 `shoulder_pitch` (ID 0, 12) 관절은 제외되었습니다.

### Left Side (0 ~ 7)
| Channel | Joint Name | ID | Description |
| :---: | :--- | :---: | :--- |
| **0** | `left_foot_roll` | 8 | 왼발 롤 (좌우) |
| **1** | `left_foot_pitch` | 7 | 왼발 피치 (앞뒤) |
| **2** | `left_knee_pitch` | 6 | 왼쪽 무릎 |
| **3** | `left_thigh_pitch` | 5 | 왼쪽 허벅지 피치 |
| **4** | `left_thigh_roll` | 4 | 왼쪽 허벅지 롤 |
| **5** | `left_elbow_roll` | 3 | 왼쪽 팔꿈치 |
| **6** | `left_shoulder_roll` | 2 | 왼쪽 어깨 롤 |
| **7** | `left_thigh_yaw` | 1 | 왼쪽 허벅지 요 (회전) |

### Right Side (8 ~ 15)
| Channel | Joint Name | ID | Description |
| :---: | :--- | :---: | :--- |
| **8** | `right_thigh_yaw` | 13 | 오른쪽 허벅지 요 (회전) |
| **9** | `right_shoulder_roll` | 14 | 오른쪽 어깨 롤 |
| **10** | `right_elbow_roll` | 15 | 오른쪽 팔꿈치 |
| **11** | `right_thigh_roll` | 16 | 오른쪽 허벅지 롤 |
| **12** | `right_thigh_pitch` | 17 | 오른쪽 허벅지 피치 |
| **13** | `right_knee_pitch` | 18 | 오른쪽 무릎 |
| **14** | `right_foot_pitch` | 19 | 오른발 피치 (앞뒤) |
| **15** | `right_foot_roll` | 20 | 오른발 롤 (좌우) |

---
**Note**: `left_shoulder_pitch` (ID 0)와 `right_shoulder_pitch` (ID 12)는 이 구현에서 제어되지 않습니다.
