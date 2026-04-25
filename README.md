# Jian English Exploration Studio

지안이 맞춤형 영어 독서·사고력·대화·글쓰기 앱 (실행 + 테스트 가능 버전)

## 핵심 변경점
- **사용자 API 키 입력 없음**: 로그인만 하면 과제 생성 가능
- **문제은행 방식 아님**: 로그인 사용자와 이전 학습기록을 반영해 매번 생성
- **최신 AI 모델 연결 구조**: 서버에서 Gemini 모델 호출(옵션), 키가 없어도 내장 생성기로 작동

## 1) 로컬 실행

```bash
python3 server.py
```

브라우저에서 `http://localhost:4173` 접속 후 이름 입력 → 로그인 → AI 과제 생성.

## 2) 자동 스모크 테스트

```bash
python3 smoke_test.py
```

검증 항목:
- `/health`
- `/api/models`
- `/api/login`
- `/api/generate-task`
- `/api/history`

## AI 연결 동작
1. 기본값: `fallback-local-ai`로 즉시 동작 (키 불필요)
2. 실제 Gemini 연결(서버 키 방식):

```bash
export GEMINI_API_KEY="your_key"
export AI_MODEL="gemini-2.5-flash"
python3 server.py
```

- 사용자 화면에서 API 키를 입력하지 않습니다.
- 로그인 후 `/api/generate-task`가 사용자 기록을 읽고 개인화 과제를 생성합니다.

## 저장되는 기록 (SQLite)
- 파일: `learning.db`
- 항목: 학습 시각, 주제, 모드, 라이브 모드, 추천 책, 읽기자료, 생성 payload

## 제공 API
- `GET /health`
- `POST /api/login`
- `GET /api/models`
- `GET /api/history`
- `POST /api/generate-task`
