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
