#!/usr/bin/env python3
"""명리 마스터 웹 서버.

외부 프레임워크 없이 표준 라이브러리 HTTP 서버로 입력 폼과 명반 생성 API를
제공합니다. Caddy는 이 서버로 reverse_proxy합니다.
"""
from __future__ import annotations

import html
import os
import re
import sys
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from scripts.calculate_chart import build_chart
from scripts.generate_html import generate_html

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "chart_template.html")
DATE_PATTERN = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")

STAR_TRAITS = {
    "자미": ("중심감", "큰 그림을 잡고 책임지는 힘이 강합니다."),
    "천기": ("전략", "생각이 빠르고 구조를 바꾸는 데 강합니다."),
    "태양": ("공개성", "사람 앞에서 역할을 맡고 에너지를 나누는 별입니다."),
    "무곡": ("실행", "결과, 돈, 책임을 현실적으로 다루는 힘이 있습니다."),
    "천동": ("회복력", "사람을 편하게 만들고 무리한 긴장을 풀어 줍니다."),
    "염정": ("몰입", "좋아하는 것에 깊게 들어가고 표현력이 살아납니다."),
    "천부": ("축적", "자원을 모으고 안정적으로 관리하는 힘이 있습니다."),
    "태음": ("감수성", "섬세한 관찰과 내면 감각이 강합니다."),
    "탐랑": ("호기심", "새로운 것을 배우고 사람을 끌어당기는 힘이 있습니다."),
    "거문": ("언어", "말, 글, 분석, 문제 제기에 강합니다."),
    "천상": ("조정", "균형을 잡고 조직 안에서 신뢰를 만듭니다."),
    "천량": ("조언", "원칙과 보호 본능이 강하고 상담자 기질이 있습니다."),
    "칠살": ("돌파", "어려운 판을 직접 뚫고 나가는 힘이 있습니다."),
    "파군": ("재건", "낡은 구조를 부수고 새 판을 짜는 별입니다."),
}


def normalize_date(raw: str) -> str:
    value = raw.strip()
    if not DATE_PATTERN.match(value):
        raise ValueError("날짜는 YYYY-M-D 또는 YYYY-MM-DD 형식으로 입력하세요.")
    year, month, day = [int(part) for part in value.split("-")]
    date(year, month, day)
    return f"{year}-{month}-{day}"


def palace_by_name(chart: dict, name: str) -> dict | None:
    return next((palace for palace in chart["palaces"] if palace["name"] == name), None)


def palace_by_decadal_age(chart: dict, age: int) -> dict | None:
    for palace in chart["palaces"]:
        decadal_range = palace.get("decadal_range", "")
        if "-" not in decadal_range:
            continue
        start, end = [int(part) for part in decadal_range.split("-", 1)]
        if start <= age <= end:
            return palace
    return None


def star_badge(palace: dict | None) -> str:
    if not palace:
        return "자료 없음"
    return "·".join(palace["major_stars"]) if palace["major_stars"] else "공궁"


def star_sentence(stars: list[str]) -> str:
    if not stars:
        return "주성이 없는 공궁이라 대궁과 실제 상황의 영향을 크게 받습니다."
    parts = []
    for star in stars[:2]:
        trait = STAR_TRAITS.get(star)
        if trait:
            parts.append(f"<em>{html.escape(star)}</em>은 {trait[1]}")
    return " ".join(parts) if parts else "별 조합은 실제 경험과 함께 보정해야 합니다."


def mutagen_sentence(chart: dict, palace_name: str) -> str:
    related = [m for m in chart["year_mutagens"] if m["palace"] == palace_name]
    if not related:
        return "생년 사화가 직접 걸리지 않아 기본 별 조합을 중심으로 봅니다."
    labels = ", ".join(f"{m['star']}{m['mutagen']}" for m in related)
    return f"이 궁에는 <strong>{html.escape(labels)}</strong> 흐름이 걸려 있어 사건성이 더 분명하게 드러납니다."


def build_dynamic_reading(chart: dict, birth_year: int) -> dict:
    today = date.today()
    korean_age = today.year - birth_year + 1

    soul = next((p for p in chart["palaces"] if "명궁" in p.get("tags", [])), None)
    career = palace_by_name(chart, "관록궁")
    wealth = palace_by_name(chart, "재백궁")
    relationship = palace_by_name(chart, "부부궁")
    current = palace_by_decadal_age(chart, korean_age) or soul
    current_branch = current["earthly_branch"] if current else chart["soul_palace_branch"]
    current_display = f"{current_branch}궁 · {star_badge(current)} · {current.get('decadal_range', '')}세" if current else ""

    soul_keywords = []
    if soul:
        for star in soul["major_stars"][:3]:
            trait = STAR_TRAITS.get(star)
            if trait:
                soul_keywords.append(trait[0])
    keyword_text = ", ".join(soul_keywords) if soul_keywords else "유연성, 환경 반응, 보정 필요"

    cards = [
        {
            "title": "명반 바탕 · 선천 기질",
            "badge": star_badge(soul),
            "full": True,
            "highlight": True,
            "body": (
                f"<strong>핵심 키워드는 {html.escape(keyword_text)}입니다.</strong> "
                f"{star_sentence(soul['major_stars'] if soul else [])}<br><br>"
                "명궁은 타고난 반응 방식과 인생을 해석하는 기본 렌즈입니다. "
                "<span class='good'>강점은 가장 먼저 반복되는 선택 패턴에서 드러납니다.</span> "
                "<span class='warn'>다만 이 해석은 보장된 결론이 아니라 현재 직업, 가족 배경, 최근 사건으로 보정해야 하는 1차 판단입니다.</span>"
            ),
            "probabilities": [
                {"label": "초기 신뢰도", "pct": 70},
                {"label": "보정 참고치", "pct": 82},
            ],
        },
        {
            "title": "일과 직업 · 관록궁",
            "badge": star_badge(career),
            "body": (
                f"{star_sentence(career['major_stars'] if career else [])}<br><br>"
                f"{mutagen_sentence(chart, '관록궁')} "
                "관록궁은 직업명 하나보다 일하는 방식, 책임을 맡는 방식, 성과를 만드는 환경을 보여줍니다."
            ),
        },
        {
            "title": "돈의 흐름 · 재백궁",
            "badge": star_badge(wealth),
            "body": (
                f"{star_sentence(wealth['major_stars'] if wealth else [])}<br><br>"
                f"{mutagen_sentence(chart, '재백궁')} "
                "재백궁은 돈을 버는 능력뿐 아니라 돈을 붙잡는 습관과 리스크 감각까지 함께 봅니다."
            ),
        },
        {
            "title": "관계와 결혼 · 부부궁",
            "badge": star_badge(relationship),
            "body": (
                f"{star_sentence(relationship['major_stars'] if relationship else [])}<br><br>"
                f"{mutagen_sentence(chart, '부부궁')} "
                "부부궁은 상대의 성격을 단정하기보다 관계에서 반복되는 거리감, 기대, 갈등 방식을 읽는 자리입니다."
            ),
        },
        {
            "title": "현재 대운 · 지금 10년의 과제",
            "badge": star_badge(current),
            "full": True,
            "teal": True,
            "body": (
                f"현재 한국식 나이 기준으로 <strong>{korean_age}세</strong> 흐름을 보며, "
                f"대운 초점은 <em>{html.escape(current_display)}</em>입니다.<br><br>"
                f"{star_sentence(current['major_stars'] if current else [])} "
                "이 시기는 새로 얻는 것보다 반복되는 과제를 어떻게 정리하는지가 중요합니다."
            ),
        },
    ]

    return {
        "current_decadal_branch": current_branch,
        "current_decadal_display": current_display,
        "cards": cards,
        "calibration_questions": [
            {"text": "현재 하는 일은 어떤 성격인가요?", "hint": "관록궁 해석을 보정합니다."},
            {"text": "최근 1-2년 사이 큰 전환이나 압박이 있었나요?", "hint": "대운 흐름을 확인합니다."},
            {"text": "관계에서 반복되는 갈등 패턴은 무엇인가요?", "hint": "부부궁 해석을 보정합니다."},
            {"text": "돈을 벌 때 확장과 안정 중 어느 쪽을 더 선택하나요?", "hint": "재백궁 활용 방식을 확인합니다."},
        ],
    }


def page_shell(content: str) -> bytes:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>명리 마스터</title>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Noto+Serif+KR:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #0A0A0F;
    --panel: #12121A;
    --line: rgba(200,169,110,.22);
    --gold: #C8A96E;
    --text: #F2EBD9;
    --muted: #B8AA90;
    --accent: #3B7A85;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    background:
      radial-gradient(ellipse at 15% 12%, rgba(59,122,133,.24), transparent 42%),
      radial-gradient(ellipse at 85% 20%, rgba(155,35,53,.18), transparent 40%),
      var(--ink);
    color: var(--text);
    font-family: 'Noto Serif KR', serif;
    word-break: keep-all;
  }}
  main {{ width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0 80px; }}
  header {{ margin-bottom: 28px; }}
  .eyebrow {{ color: var(--gold); letter-spacing: 4px; font-size: 12px; margin-bottom: 10px; }}
  h1 {{ font-family: 'Gowun Batang', serif; font-size: clamp(38px, 7vw, 66px); line-height: 1.1; margin: 0; color: var(--gold); }}
  .sub {{ color: var(--muted); margin-top: 14px; line-height: 1.8; max-width: 720px; }}
  form {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    background: rgba(18,18,26,.9);
    border: 1px solid var(--line);
    padding: 22px;
  }}
  label {{ display: flex; flex-direction: column; gap: 8px; color: var(--muted); font-size: 12px; letter-spacing: 1px; }}
  input, select, button {{
    width: 100%;
    min-height: 44px;
    border: 1px solid rgba(200,169,110,.25);
    background: #0f0f16;
    color: var(--text);
    padding: 0 12px;
    font: inherit;
  }}
  .check {{ flex-direction: row; align-items: center; padding-top: 25px; }}
  .check input {{ width: 18px; min-height: 18px; }}
  button {{
    cursor: pointer;
    background: linear-gradient(135deg, var(--gold), #9f7f43);
    color: #111;
    font-weight: 700;
    border: 0;
    align-self: end;
  }}
  .error {{
    border: 1px solid rgba(255,120,90,.45);
    background: rgba(155,35,53,.16);
    color: #ffb29a;
    padding: 16px;
    margin-bottom: 18px;
  }}
  .sample {{ margin-top: 20px; color: var(--muted); font-size: 13px; }}
  .sample a {{ color: var(--gold); }}
  @media (max-width: 760px) {{
    form {{ grid-template-columns: 1fr 1fr; }}
    button {{ grid-column: 1 / -1; }}
  }}
  @media (max-width: 520px) {{
    main {{ width: min(100% - 22px, 980px); padding-top: 32px; }}
    form {{ grid-template-columns: 1fr; padding: 16px; }}
    .check {{ padding-top: 0; }}
  }}
</style>
</head>
<body>
<main>{content}</main>
</body>
</html>""".encode("utf-8")


def render_form(error: str = "") -> bytes:
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    hours = "\n".join(
        f'<option value="{idx}" {"selected" if idx == 1 else ""}>{label}</option>'
        for idx, label in [
            (0, "조자시 23:00-00:00"),
            (1, "축시 01:00-03:00"),
            (2, "인시 03:00-05:00"),
            (3, "묘시 05:00-07:00"),
            (4, "진시 07:00-09:00"),
            (5, "사시 09:00-11:00"),
            (6, "오시 11:00-13:00"),
            (7, "미시 13:00-15:00"),
            (8, "신시 15:00-17:00"),
            (9, "유시 17:00-19:00"),
            (10, "술시 19:00-21:00"),
            (11, "해시 21:00-23:00"),
            (12, "야자시 23:00-00:00"),
        ]
    )
    return page_shell(f"""
<header>
  <div class="eyebrow">자미두수 명반 생성기</div>
  <h1>명리 마스터</h1>
  <div class="sub">생년월일시를 입력하면 Python 계산기로 12궁과 사화를 산출하고, 규칙 기반 한국어 명반 리포트를 즉시 생성합니다. 현재 웹앱은 외부 AI 모델을 호출하지 않습니다.</div>
</header>
{error_html}
<form method="post" action="/generate">
  <label>날짜
    <input name="birth_date" type="date" value="1991-08-15" required>
  </label>
  <label>달력
    <select name="calendar">
      <option value="solar" selected>양력</option>
      <option value="lunar">음력</option>
    </select>
  </label>
  <label>시진
    <select name="hour">{hours}</select>
  </label>
  <label>성별
    <select name="gender">
      <option value="남" selected>남성</option>
      <option value="여">여성</option>
    </select>
  </label>
  <label class="check">
    <input name="leap" type="checkbox" value="1">
    음력 윤달
  </label>
  <button type="submit">명반 생성</button>
</form>
<div class="sample">샘플 리포트는 <a href="/sample">여기</a>에서 바로 볼 수 있습니다.</div>
""")


class MingliHandler(BaseHTTPRequestHandler):
    server_version = "MingliMaster/1.0"

    def send_html(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_html(render_form())
            return
        if self.path == "/health":
            body = b"ok"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/sample":
            with open(os.path.join(BASE_DIR, "public", "index.html"), "rb") as sample_file:
                self.send_html(sample_file.read())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192:
                raise ValueError("요청이 너무 큽니다.")
            payload = self.rfile.read(length).decode("utf-8")
            form = parse_qs(payload)
            birth_date = normalize_date(form.get("birth_date", [""])[0])
            calendar = form.get("calendar", ["solar"])[0]
            hour = int(form.get("hour", ["1"])[0])
            gender = form.get("gender", ["남"])[0]
            is_lunar = calendar == "lunar"
            is_leap = form.get("leap", [""])[0] == "1"

            if hour < 0 or hour > 12:
                raise ValueError("시진 값은 0부터 12 사이여야 합니다.")

            chart = build_chart(birth_date, hour, gender, is_lunar=is_lunar, is_leap=is_leap)
            birth_year = int(birth_date.split("-", 1)[0])
            reading = build_dynamic_reading(chart, birth_year)
            output = generate_html(chart, reading, TEMPLATE_PATH).encode("utf-8")
            self.send_html(output)
        except Exception as exc:
            self.send_html(render_form(str(exc)), HTTPStatus.BAD_REQUEST)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3337
    server = ThreadingHTTPServer((host, port), MingliHandler)
    print(f"명리 마스터 서버 시작: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
