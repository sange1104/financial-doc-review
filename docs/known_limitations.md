# Known Limitations

## OCR Name Extraction

현재 이름 추출은 위치 정보(bbox) 없이 텍스트 순서 기반 heuristic을 사용한다.

### 동작 방식

1. "주민등록증" 텍스트를 `doc_title`로 인식
2. 그 이후 첫 번째 high-confidence 텍스트를 `name`으로 판정

### 한계

- OCR line order가 깨질 경우 이름이 아닌 텍스트를 오인식할 수 있음
- 문서 레이아웃이 다를 경우 (예: 가로/세로 배치 차이) 순서 가정이 깨짐

### 후속 개선

- bbox 좌표 기반 후보 선택: `doc_title` 아래 영역에서 이름 필드를 탐색
- 문서 타입별 필드 위치 템플릿 정의

## 통장사본 이름 추출

현재 통장사본의 이름 추출은 "님" 텍스트 기반 heuristic을 사용한다.

### 한계

- "님"이 별도 줄로 나오지 않거나 없는 경우 이름을 추출하지 못함
- 우리은행 통장사본 등 일부 포맷에서 이름이 review로 빠짐

### 후속 개선

- "계좌번호" 라벨 근처의 이름 후보를 bbox 기반으로 탐색
- 은행별 레이아웃 패턴 매칭

## Glare 감지

MVP에서는 glare 감지를 비활성화했다 (`glare_detected = False`).

### 이유

- 문서 배경(특히 통장사본)이 흰색인 경우와 실제 glare를 단순 픽셀 비율만으로 구분할 수 없음
- 밝은 배경의 통장사본이 glare로 오탐되어 정상 문서가 retake 판정을 받음

### 후속 개선

- gradient 기반 glare 감지 (glare는 국소적 밝기 변화가 급격함)
- 학습 기반 glare classifier
