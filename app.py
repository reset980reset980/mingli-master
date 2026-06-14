#!/usr/bin/env python3
"""명리 마스터 웹 서버.

원본 Skill 흐름을 웹에서 실행합니다.

1. 생년월일시 입력
2. iztro-py로 명반 JSON 계산
3. Skill/참고 문서와 명반 JSON을 LLM에 전달해 reading.json 생성
4. HTML 보고서 저장
5. 보정 답변 제출 시 새 버전 보고서로 누적 저장
"""
from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.calculate_chart import build_chart
from scripts.generate_html import generate_html

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "chart_template.html"
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = DATA_DIR / "reports.db"
READING_SCHEMA_PATH = BASE_DIR / "reading_schema.json"
DATE_PATTERN = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
CODEX_TIMEOUT_SECONDS = int(os.environ.get("MINGLI_CODEX_TIMEOUT", "300"))


def load_local_env() -> None:
    """서비스 환경에 없는 키를 로컬 .env에서 보충합니다."""
    for env_path in (BASE_DIR / ".env", Path("/home/reset980/.env")):
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_date(raw: str) -> str:
    value = raw.strip()
    if not DATE_PATTERN.match(value):
        raise ValueError("날짜는 YYYY-M-D 또는 YYYY-MM-DD 형식으로 입력하세요.")
    year, month, day = [int(part) for part in value.split("-")]
    date(year, month, day)
    return f"{year}-{month}-{day}"


def init_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                person_name TEXT,
                birth_date TEXT NOT NULL,
                calendar TEXT NOT NULL,
                hour INTEGER NOT NULL,
                gender TEXT NOT NULL,
                leap INTEGER NOT NULL,
                focus TEXT,
                calibration_json TEXT,
                chart_json TEXT NOT NULL,
                reading_json TEXT NOT NULL,
                html_path TEXT NOT NULL,
                model TEXT NOT NULL
            )
            """
        )


def db_row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def save_report(
    *,
    parent_id: str | None,
    person_name: str,
    birth_date: str,
    calendar: str,
    hour: int,
    gender: str,
    leap: bool,
    focus: str,
    calibration: dict,
    chart: dict,
    reading: dict,
    model: str,
) -> str:
    report_id = uuid.uuid4().hex[:12]
    created_at = now_iso()
    display_name = person_name.strip() or "이름 없음"
    title = f"{display_name} · {birth_date} · {reading.get('current_decadal_display', '명반 해석')}"
    reading["report_id"] = report_id
    reading["calibration_action"] = f"/reports/{report_id}/calibrate"
    body = generate_html(chart, reading, str(TEMPLATE_PATH))
    body = body.replace(
        "</div>\n</body>",
        f'<div class="report-nav"><a href="/">새 분석</a><a href="/reports">과거 보고서</a></div>\n</div>\n</body>',
    )
    html_path = REPORT_DIR / f"{report_id}.html"
    html_path.write_text(body, encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO reports (
                id, parent_id, created_at, title, person_name, birth_date, calendar,
                hour, gender, leap, focus, calibration_json, chart_json, reading_json,
                html_path, model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                parent_id,
                created_at,
                title,
                person_name,
                birth_date,
                calendar,
                hour,
                gender,
                int(leap),
                focus,
                json.dumps(calibration, ensure_ascii=False),
                json.dumps(chart, ensure_ascii=False),
                json.dumps(reading, ensure_ascii=False),
                str(html_path),
                model,
            ),
        )
    return report_id


def get_report(report_id: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return db_row_to_dict(row) if row else None


def list_reports(limit: int = 80) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [db_row_to_dict(row) for row in rows]


def read_context_file(path: str, max_chars: int = 14000) -> str:
    text = (BASE_DIR / path).read_text(encoding="utf-8", errors="ignore")
    return text[:max_chars]


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def call_codex(prompt: str) -> tuple[dict, str]:
    """Codex CLI로 Skill 기반 reading.json을 생성합니다."""
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as output_file:
        output_path = output_file.name
    command = [
        "codex",
        "exec",
        "--cd",
        str(BASE_DIR),
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(READING_SCHEMA_PATH),
        "--output-last-message",
        output_path,
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=CODEX_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"Codex CLI 해석 생성 실패: {detail[-1200:]}")
        output = Path(output_path).read_text(encoding="utf-8", errors="ignore")
        if not output.strip():
            output = completed.stdout
        return extract_json(output), "codex-cli"
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Codex CLI 해석 생성 시간이 {CODEX_TIMEOUT_SECONDS}초를 초과했습니다.") from exc
    finally:
        try:
            Path(output_path).unlink()
        except OSError:
            pass


def build_ai_prompt(
    *,
    chart: dict,
    person_name: str,
    birth_date: str,
    calendar: str,
    hour: int,
    gender: str,
    focus: str,
    calibration: dict | None = None,
    previous_reading: dict | None = None,
) -> str:
    current_year = date.today().year
    return f"""
너는 한국어 자미두수 명반 해석 에이전트다. 아래 Skill 지침과 참고 문서를 따르되,
결정론, 공포 조성, 의료/법률/투자 단정은 금지한다.

반드시 유효한 JSON 객체 하나만 출력한다. Markdown 코드펜스는 쓰지 않는다.
파일을 읽거나 수정하지 말고, 아래 프롬프트에 포함된 자료만 사용한다.

JSON 스키마:
{{
  "current_decadal_branch": "현재 대운 궁의 지지. 예: 진",
  "current_decadal_display": "현재 대운 표시. 예: 진궁 · 자미·천상 · 42-51세",
  "cards": [
    {{
      "title": "명반 바탕 · 선천 기질",
      "badge": "주요 별",
      "full": true,
      "highlight": true,
      "body": "HTML 허용: <strong>, <em>, <span class='warn'>, <span class='good'>, <br>",
      "probabilities": [
        {{"label": "초기 신뢰도", "pct": 70}},
        {{"label": "보정 참고치", "pct": 82}}
      ]
    }}
  ],
  "calibration_questions": [
    {{"text": "질문", "hint": "왜 묻는지"}}
  ]
}}

카드는 반드시 5개 이상 작성한다:
1. 명반 바탕
2. 일과 직업
3. 돈의 흐름
4. 관계와 결혼
5. 현재 대운
필요하면 건강/가족/최근 3년 흐름 카드를 추가한다.

사용자 입력:
- 이름: {person_name or "미입력"}
- 날짜: {birth_date}
- 달력: {calendar}
- 시진 번호: {hour}
- 성별: {gender}
- 관심 주제: {focus or "전체"}
- 현재 연도: {current_year}

보정 답변:
{json.dumps(calibration or {}, ensure_ascii=False, indent=2)}

이전 해석(JSON, 보정 재분석일 때만 참고):
{json.dumps(previous_reading or {}, ensure_ascii=False, indent=2)[:12000]}

명반 계산 JSON:
{json.dumps(chart, ensure_ascii=False, indent=2)}

SKILL.md:
{read_context_file("SKILL.md")}

해석 문체 가이드:
{read_context_file("references/interpretation_guide.md")}

별 참고:
{read_context_file("references/stars_reference.md")}

사화 참고:
{read_context_file("references/four_hua_reference.md")}
"""


def page_shell(content: str, title: str = "명리 마스터") -> bytes:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Noto+Serif+KR:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{ --ink:#0A0A0F; --panel:#12121A; --line:rgba(200,169,110,.22); --gold:#C8A96E; --text:#F2EBD9; --muted:#B8AA90; --accent:#3B7A85; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; background:radial-gradient(ellipse at 15% 12%, rgba(59,122,133,.24), transparent 42%), radial-gradient(ellipse at 85% 20%, rgba(155,35,53,.18), transparent 40%), var(--ink); color:var(--text); font-family:'Noto Serif KR',serif; word-break:keep-all; }}
  main {{ width:min(1040px, calc(100% - 32px)); margin:0 auto; padding:56px 0 80px; }}
  header {{ margin-bottom:28px; }}
  .eyebrow {{ color:var(--gold); letter-spacing:4px; font-size:12px; margin-bottom:10px; }}
  h1 {{ font-family:'Gowun Batang',serif; font-size:clamp(38px,7vw,66px); line-height:1.1; margin:0; color:var(--gold); }}
  .sub {{ color:var(--muted); margin-top:14px; line-height:1.8; max-width:760px; }}
  form, .panel {{ background:rgba(18,18,26,.92); border:1px solid var(--line); padding:22px; }}
  form.grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }}
  label {{ display:flex; flex-direction:column; gap:8px; color:var(--muted); font-size:12px; letter-spacing:1px; }}
  input, select, textarea, button {{ width:100%; border:1px solid rgba(200,169,110,.25); background:#0f0f16; color:var(--text); padding:10px 12px; font:inherit; }}
  input, select, button {{ min-height:44px; }}
  textarea {{ min-height:92px; resize:vertical; line-height:1.7; }}
  .wide {{ grid-column:1 / -1; }}
  .check {{ flex-direction:row; align-items:center; padding-top:25px; }}
  .check input {{ width:18px; min-height:18px; }}
  button {{ cursor:pointer; background:linear-gradient(135deg,var(--gold),#9f7f43); color:#111; font-weight:700; border:0; align-self:end; }}
  .error {{ border:1px solid rgba(255,120,90,.45); background:rgba(155,35,53,.16); color:#ffb29a; padding:16px; margin-bottom:18px; }}
  .nav {{ display:flex; gap:14px; margin:22px 0; flex-wrap:wrap; }}
  a {{ color:var(--gold); }}
  .report-list {{ display:grid; gap:12px; margin-top:20px; }}
  .report-item {{ border:1px solid rgba(200,169,110,.16); background:rgba(18,18,26,.7); padding:16px; }}
  .report-item div {{ color:var(--muted); font-size:13px; margin-top:6px; }}
  @media (max-width:760px) {{ form.grid {{ grid-template-columns:1fr 1fr; }} button,.wide {{ grid-column:1/-1; }} }}
  @media (max-width:520px) {{ main {{ width:min(100% - 22px, 1040px); padding-top:32px; }} form.grid {{ grid-template-columns:1fr; padding:16px; }} .check {{ padding-top:0; }} }}
</style>
</head>
<body><main>{content}</main></body></html>""".encode("utf-8")


def render_home(error_message: str = "") -> bytes:
    reports = list_reports(8)
    error_html = f'<div class="error">{html.escape(error_message)}</div>' if error_message else ""
    hours = "\n".join(
        f'<option value="{idx}" {"selected" if idx == 1 else ""}>{label}</option>'
        for idx, label in [
            (0, "조자시 23:00-00:00"), (1, "축시 01:00-03:00"),
            (2, "인시 03:00-05:00"), (3, "묘시 05:00-07:00"),
            (4, "진시 07:00-09:00"), (5, "사시 09:00-11:00"),
            (6, "오시 11:00-13:00"), (7, "미시 13:00-15:00"),
            (8, "신시 15:00-17:00"), (9, "유시 17:00-19:00"),
            (10, "술시 19:00-21:00"), (11, "해시 21:00-23:00"),
            (12, "야자시 23:00-00:00"),
        ]
    )
    recent = render_report_list(reports, heading="최근 보고서")
    return page_shell(f"""
<header>
  <div class="eyebrow">자미두수 AI 명반 보고서</div>
  <h1>명리 마스터</h1>
  <div class="sub">생년월일시를 입력하면 명반을 계산하고, Skill 지침과 참고 문서를 적용해 AI가 한국어 HTML 보고서를 작성합니다. 보정 답변을 제출하면 새 버전 보고서로 누적 저장됩니다.</div>
</header>
<div class="nav"><a href="/reports">과거 보고서 전체 보기</a></div>
{error_html}
<form class="grid" method="post" action="/generate">
  <label>이름 또는 구분명
    <input name="person_name" type="text" value="" placeholder="예: 홍길동, 1차 상담">
  </label>
  <label>날짜
    <input name="birth_date" type="date" value="1991-08-15" required>
  </label>
  <label>달력
    <select name="calendar"><option value="solar" selected>양력</option><option value="lunar">음력</option></select>
  </label>
  <label>시진
    <select name="hour">{hours}</select>
  </label>
  <label>성별
    <select name="gender"><option value="남" selected>남성</option><option value="여">여성</option></select>
  </label>
  <label class="check">
    <input name="leap" type="checkbox" value="1"> 음력 윤달
  </label>
  <label class="wide">중점 질문
    <textarea name="focus" placeholder="예: 직업과 돈 흐름 중심으로 봐줘. 최근 2년 변화도 같이 봐줘."></textarea>
  </label>
  <button class="wide" type="submit">AI 보고서 생성</button>
</form>
{recent}
""")


def render_report_list(reports: list[dict], heading: str = "과거 보고서") -> str:
    if not reports:
        return f'<section class="panel report-list"><h2>{html.escape(heading)}</h2><p class="sub">저장된 보고서가 없습니다.</p></section>'
    items = []
    for report in reports:
        items.append(
            f'''<article class="report-item">
  <a href="/reports/{report["id"]}">{html.escape(report["title"])}</a>
  <div>{html.escape(report["created_at"])} · {html.escape(report["model"])} · ID {html.escape(report["id"])}</div>
</article>'''
        )
    return f'<section class="report-list"><h2>{html.escape(heading)}</h2>{"".join(items)}</section>'


def parse_form(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 20000:
        raise ValueError("요청이 너무 큽니다.")
    payload = handler.rfile.read(length).decode("utf-8")
    form = parse_qs(payload)
    return {key: values[0] if values else "" for key, values in form.items()}


class MingliHandler(BaseHTTPRequestHandler):
    server_version = "MingliMaster/2.0"

    def send_html(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/":
            self.send_html(render_home())
            return
        if path == "/health":
            body = b"ok"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/reports":
            content = '<div class="nav"><a href="/">새 분석</a></div>' + render_report_list(list_reports(200), "과거 보고서")
            self.send_html(page_shell(content, "과거 보고서"))
            return
        match = re.match(r"^/reports/([a-f0-9]{12})$", path)
        if match:
            report = get_report(match.group(1))
            if not report:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_html(Path(report["html_path"]).read_bytes())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/generate":
                self.handle_generate()
                return
            match = re.match(r"^/reports/([a-f0-9]{12})/calibrate$", path)
            if match:
                self.handle_calibrate(match.group(1))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_html(render_home(str(exc)), HTTPStatus.BAD_REQUEST)

    def handle_generate(self) -> None:
        form = parse_form(self)
        birth_date = normalize_date(form.get("birth_date", ""))
        calendar = form.get("calendar", "solar")
        hour = int(form.get("hour", "1"))
        gender = form.get("gender", "남")
        leap = form.get("leap", "") == "1"
        person_name = form.get("person_name", "").strip()
        focus = form.get("focus", "").strip()
        if hour < 0 or hour > 12:
            raise ValueError("시진 값은 0부터 12 사이여야 합니다.")
        is_lunar = calendar == "lunar"
        chart = build_chart(birth_date, hour, gender, is_lunar=is_lunar, is_leap=leap)
        reading, model = call_codex(
            build_ai_prompt(
                chart=chart,
                person_name=person_name,
                birth_date=birth_date,
                calendar=calendar,
                hour=hour,
                gender=gender,
                focus=focus,
            )
        )
        report_id = save_report(
            parent_id=None,
            person_name=person_name,
            birth_date=birth_date,
            calendar=calendar,
            hour=hour,
            gender=gender,
            leap=leap,
            focus=focus,
            calibration={},
            chart=chart,
            reading=reading,
            model=model,
        )
        self.redirect(f"/reports/{report_id}")

    def handle_calibrate(self, report_id: str) -> None:
        previous = get_report(report_id)
        if not previous:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        form = parse_form(self)
        calibration = {
            key: value.strip()
            for key, value in form.items()
            if key.startswith("calibration_") and value.strip()
        }
        if not calibration:
            raise ValueError("보정 답변을 하나 이상 입력하세요.")
        chart = json.loads(previous["chart_json"])
        previous_reading = json.loads(previous["reading_json"])
        reading, model = call_codex(
            build_ai_prompt(
                chart=chart,
                person_name=previous["person_name"] or "",
                birth_date=previous["birth_date"],
                calendar=previous["calendar"],
                hour=int(previous["hour"]),
                gender=previous["gender"],
                focus=previous["focus"] or "",
                calibration=calibration,
                previous_reading=previous_reading,
            )
        )
        new_id = save_report(
            parent_id=report_id,
            person_name=previous["person_name"] or "",
            birth_date=previous["birth_date"],
            calendar=previous["calendar"],
            hour=int(previous["hour"]),
            gender=previous["gender"],
            leap=bool(previous["leap"]),
            focus=previous["focus"] or "",
            calibration=calibration,
            chart=chart,
            reading=reading,
            model=model,
        )
        self.redirect(f"/reports/{new_id}")

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    init_storage()
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3337
    server = ThreadingHTTPServer((host, port), MingliHandler)
    print(f"명리 마스터 서버 시작: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
