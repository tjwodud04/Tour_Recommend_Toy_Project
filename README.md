### Tour Recommend Toy Project
사용자 질의를 받아 지역/대분류를 추출하고, 한국관광공사 TourAPI로 관광지를 조회해 카드 형태로 보여줍니다.

### 출력 예시
<img width="1443" height="599" alt="image" src="https://github.com/user-attachments/assets/bc3da794-6dfd-481b-854b-c46428d02fe2" />


### 동작 방식

1. 사용자가 질의 입력 (예: “제주 자연”)
2. OpenAI로 `region`, `cat1`(대분류) 1개씩 추출
3. `areaCode2`로 지역명을 지역코드로 변환
4. `areaBasedList2`로 목록 조회(대표이미지 보장 정렬 + cat1 필터)
5. 상세(`detailCommon2`)로 overview/homepage 보강, 한 줄 요약 생성
6. 이미지 검증(`firstimage2→firstimage→detailImage2`) 후 카드로 렌더링
7. 질의 임베딩을 경량 JSONL 캐시에 저장(재질의 시 재사용)

### 주요 구성 파일

* `app.py` : Streamlit UI
* `data_service.py` : TourAPI 호출/정규화/요약
* `search_service.py` : 임베딩 캐시(JSONL) + 조회 흐름
* `embedding_service.py` : OpenAI 임베딩
* `config.py` : 환경설정(.env)

### 요구사항

* Python 3.10+
* OpenAI API 키
* 한국관광공사 TourAPI 키(Encoding Key or Decoding Key)

## 설치 & 실행

```bash
# 가상환경 권장
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\activate

git clone https://github.com/tjwodud04/Tour_Recommend_Toy_Project.git
cd ./Tour_Recommend_Toy_Project
pip install requirements.txt

# 환경변수 설정 (example.env 파일 .env로 변경)
OPENAI_API_KEY=sk-...
KOREA_TOURISM_API_KEY=...  # 공백 없이

# 실행
python -m streamlit run app.py
```

### Streamlit 사용법

* 좌측 메뉴 → **관광지 찾기**
* 예시 질의:
  * `제주 자연`
  * `부산 박물관`
  * `강릉 카페거리`
* 결과 카드: 썸네일 / 이름 / 한 줄 요약 / 주소 / 홈페이지 링크
