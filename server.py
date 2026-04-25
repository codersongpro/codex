#!/usr/bin/env python3
import json
import os
import secrets
import sqlite3
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.path.join(os.path.dirname(__file__), "learning.db")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", "4173"))

SESSIONS = {}


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            learned_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            mode TEXT NOT NULL,
            live_mode TEXT NOT NULL,
            book_intro TEXT,
            book_advanced TEXT,
            reading_title TEXT,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


def find_or_create_user(name: str):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        conn.close()
        return dict(row)
    now = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO users(name, created_at) VALUES(?, ?)", (name, now))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return {"id": user_id, "name": name}


def get_history(user_id: int, limit: int = 30):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT learned_at, topic, mode, live_mode, book_intro, book_advanced, reading_title, payload_json
        FROM learning_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        items.append(item)
    return items


def save_history(user_id: int, topic: str, mode: str, live_mode: str, payload: dict):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO learning_history(
          user_id, learned_at, topic, mode, live_mode, book_intro, book_advanced, reading_title, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            datetime.utcnow().isoformat(),
            topic,
            mode,
            live_mode,
            payload.get("books", [{}])[0].get("title", ""),
            payload.get("books", [{}, {}])[1].get("title", ""),
            payload.get("reading", {}).get("title", ""),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def fallback_generation(topic, mode, live_mode, history):
    topic_map = {
        "math_science": "수학/과학",
        "history_humanities": "역사/인문",
        "philosophy_ethics": "철학/윤리",
        "literature": "문학",
    }
    books_by_topic = {
        "math_science": [
            {"title": "National Geographic Readers: Planets", "lang": "영어", "step": "입문용"},
            {"title": "Why? 우주", "lang": "한글", "step": "확장용"},
        ],
        "history_humanities": [
            {"title": "Who Was King Sejong?", "lang": "영어", "step": "입문용"},
            {"title": "세종대왕", "lang": "한글", "step": "확장용"},
        ],
        "philosophy_ethics": [
            {"title": "What If Everybody Did That?", "lang": "영어", "step": "입문용"},
            {"title": "어린이를 위한 철학", "lang": "한글", "step": "확장용"},
        ],
        "literature": [
            {"title": "Frog and Toad Are Friends", "lang": "영어", "step": "입문용"},
            {"title": "강아지똥", "lang": "한글", "step": "확장용"},
        ],
    }
    reading_by_topic = {
        "math_science": {
            "title": "How Stars Help Us Learn",
            "text": [
                "Stars are far away, but we can still see them.",
                "The Sun is a star close to Earth.",
                "Some stars look red. Some stars look blue.",
                "Scientists compare star colors.",
                "They ask why stars look different.",
                "We learn patterns from the sky.",
            ],
            "summary_ko": "별을 관찰하면 색과 패턴을 비교하며 과학적 질문을 할 수 있어요.",
            "keywords": ["star(별)", "color(색)", "pattern(패턴)", "compare(비교)", "question(질문)"],
        },
        "history_humanities": {
            "title": "Life in the Past",
            "text": [
                "Long ago, children learned in different ways.",
                "Some wrote with brushes.",
                "Families cooked without electricity.",
                "People shared stories at night.",
                "We compare past and present life.",
                "History helps us understand people.",
            ],
            "summary_ko": "옛날과 지금의 생활을 비교하며 사람과 문화의 변화를 이해해요.",
            "keywords": ["past(과거)", "present(현재)", "family(가족)", "story(이야기)", "compare(비교)"],
        },
        "philosophy_ethics": {
            "title": "Fair Sharing",
            "text": [
                "Two friends have one snack.",
                "Both friends are hungry.",
                "They talk about a fair way to share.",
                "One idea is half and half.",
                "Another idea is taking turns.",
                "They ask, what is fair?",
            ],
            "summary_ko": "공정함을 실제 상황으로 생각하고, 이유를 말하는 연습을 해요.",
            "keywords": ["fair(공정)", "share(나누다)", "turn(순서)", "reason(이유)", "choice(선택)"],
        },
        "literature": {
            "title": "A Small Seed Story",
            "text": [
                "A seed sleeps in the soil.",
                "Rain comes and the seed wakes up.",
                "It grows into a small plant.",
                "A child watches it every day.",
                "The child feels hope and joy.",
                "Stories help us feel and think.",
            ],
            "summary_ko": "이야기를 통해 감정과 의미를 말하고 상상력을 키워요.",
            "keywords": ["seed(씨앗)", "grow(자라다)", "feel(느끼다)", "hope(희망)", "story(이야기)"],
        },
    }

    seen = {h.get("reading_title") for h in history if h.get("reading_title")}
    reading = reading_by_topic[topic]
    if reading["title"] in seen:
        reading = dict(reading)
        reading["title"] = f"{reading['title']} - New Angle"
        reading["text"] = reading["text"][:3] + ["Today we look at a new angle of the same topic."] + reading["text"][3:]

    return {
        "topic": topic_map.get(topic, topic),
        "reason": "지안이의 비교·패턴·구조화 강점을 활용하고, 한 번에 한 과제로 작업기억 부담을 낮춥니다.",
        "mode": mode,
        "books": books_by_topic[topic],
        "reading": reading,
        "understanding_questions": [
            "What is one key idea?",
            "What did you learn first?",
            "Can you explain in one sentence?",
        ],
        "conversation_questions": [
            "What do you think?",
            "Which part was interesting?",
            "Why is this important?",
        ],
        "parent_questions": [
            "Why does this topic matter in real life?",
            "What would you do in this situation?",
            "Do you agree with the adult's idea? Why?",
        ],
        "working_memory": "Remember 2 Words → Say It Again → One-sentence summary",
        "writing": {
            "topic": "Today’s Topic Reflection",
            "big_question": "Why is this topic important?",
            "starters": [
                "I learned that ...",
                "I think ...",
                "My favorite part was ...",
                "This is important because ...",
            ],
        },
        "worksheet_note": "이 워크시트는 A4 세로 PDF로 저장 후 출력하여 바로 사용할 수 있도록 설계함.",
        "live_mode": live_mode,
        "source": "fallback-local-ai",
    }


def generate_with_gemini(topic, mode, live_mode, history):
    history_titles = [h.get("reading_title") for h in history if h.get("reading_title")]
    prompt = f"""
You are an English Exploration Coach for a grade-2 learner in Korea.
Return STRICT JSON with keys:
topic, reason, mode, books(array of 2 with title/lang/step),
reading(title,text[5-10],summary_ko,keywords[5]),
understanding_questions[3], conversation_questions[3], parent_questions[3],
working_memory, writing(topic,big_question,starters[4]), worksheet_note, live_mode, source.
Constraints:
- Avoid repeating past reading titles: {history_titles}
- Keep sentences short and clear.
- One main task at a time.
- Include English + Korean support.
Requested topic={topic}, mode={mode}, live_mode={live_mode}
"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        data = json.loads(res.read().decode("utf-8"))
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    payload = json.loads(text)
    payload["source"] = f"gemini:{AI_MODEL}"
    return payload


class AppHandler(SimpleHTTPRequestHandler):
    def json_response(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def get_user_id_from_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.split(" ", 1)[1]
        return SESSIONS.get(token)

    def do_GET(self):
        if self.path == "/health":
            self.json_response({"ok": True, "time": datetime.utcnow().isoformat()})
            return
        if self.path == "/api/models":
            self.json_response({
                "models": [AI_MODEL],
                "provider": "gemini" if GEMINI_API_KEY else "fallback-local-ai",
                "requires_user_api_input": False,
            })
            return
        if self.path == "/api/history":
            user_id = self.get_user_id_from_auth()
            if not user_id:
                self.json_response({"error": "unauthorized"}, status=401)
                return
            self.json_response({"items": get_history(user_id)})
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/login":
            body = self.read_json_body()
            name = (body.get("name") or "").strip()
            if len(name) < 2:
                self.json_response({"error": "name_too_short"}, status=400)
                return
            user = find_or_create_user(name)
            token = secrets.token_urlsafe(24)
            SESSIONS[token] = user["id"]
            self.json_response({"token": token, "user": user})
            return

        if self.path == "/api/generate-task":
            user_id = self.get_user_id_from_auth()
            if not user_id:
                self.json_response({"error": "unauthorized"}, status=401)
                return

            body = self.read_json_body()
            topic = body.get("topic", "math_science")
            mode = body.get("mode", "Depth")
            live_mode = body.get("live_mode", "Read with me")
            history = get_history(user_id)

            payload = None
            if GEMINI_API_KEY:
                try:
                    payload = generate_with_gemini(topic, mode, live_mode, history)
                except Exception:
                    payload = fallback_generation(topic, mode, live_mode, history)
            else:
                payload = fallback_generation(topic, mode, live_mode, history)

            save_history(user_id, topic, mode, live_mode, payload)
            self.json_response(payload)
            return

        self.json_response({"error": "not_found"}, status=404)


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), AppHandler)
    print(f"Server running at http://localhost:{PORT}")
    print(f"AI provider: {'gemini' if GEMINI_API_KEY else 'fallback-local-ai'} ({AI_MODEL})")
    server.serve_forever()
