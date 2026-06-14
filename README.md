# 명리 마스터.skill

![](assets/musk-mingpan.jpg)

> *엘론 머스크 명반 예시*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Standard-green)](https://agentskills.io)
[![Python](https://img.shields.io/badge/Python-3.8+-blue)](https://python.org)
[![iztro-py](https://img.shields.io/badge/Powered%20by-iztro--py-C8A96E)](https://github.com/spyfree/iztro-py)

**생년월일시를 입력하면 자미두수 명반을 계산하고, 한국어 해석 리포트 HTML을 생성합니다.**

자미삼합, 중주파 화기 추적, 손금 교차 검증 관점을 함께 사용합니다. 계산은 Python과 `iztro-py`가 담당하고, 해석은 AI가 따뜻하고 명확한 한국어 문장으로 정리합니다.

[효과 예시](#효과-예시) · [설치](#설치) · [사용](#사용) · [작동 방식](#작동-방식) · [저장소 구조](#저장소-구조)

---

## 효과 예시

생년월일시를 넣으면 명리 마스터가 자동으로 명반을 계산하고 시각화된 리포트를 만듭니다. 예시는 엘론 머스크 명반입니다.

> **"천기와 태음이 인궁에서 명궁을 이루면 핵심은 머리로 세계를 바꾸려는 사람입니다."**
>
> 천기는 전략가의 별이라 늘 다음 수를 생각합니다. 태음은 달의 별이라 내면 감각과 직관이 강합니다. 두 별이 겹치면 계속 생각하고, 계속 가정하고, 기존 틀을 의심하는 사람이 됩니다.
>
> 인궁의 천기·태음은 현 상태에 쉽게 만족하지 않습니다. 이미 있는 틀을 조금 고치는 쪽보다, 틀 자체가 맞는지부터 묻는 쪽에 가깝습니다.

각 리포트에는 다음 내용이 들어갑니다.

- **명반 바탕**: 선천 기질과 성격의 중심축
- **일과 돈**: 관록궁과 재백궁의 구조
- **관계와 결혼**: 부부궁이 보여주는 관계 패턴
- **현재 대운**: 지금 10년의 핵심 과제
- **손금 교차 검증**: 손금 특징과 명반의 일치/충돌 비교(선택)

**[전체 예시 이미지 보기](https://github.com/learnwithu/mingli-master/blob/main/assets/musk-mingpan.jpg)**

---

## 설치

명리 마스터는 Agent Skills 표준을 따릅니다. Claude Code, Codex CLI, Cursor 등 skills 호환 런타임에서 사용할 수 있습니다.

### 필수 의존성

정확한 명반 계산을 위해 [iztro-py](https://github.com/spyfree/iztro-py)를 사용합니다.

```bash
python3 -m pip install iztro-py --user --break-system-packages
```

### 방법 1: 한 줄 설치

사용 중인 에이전트에게 다음처럼 요청합니다.

```text
이 skill을 설치해줘: https://github.com/learnwithu/mingli-master
```

또는 범용 CLI 설치기를 사용할 수 있습니다.

```bash
npx skills add learnwithu/mingli-master
```

### 방법 2: 수동 설치

| 런타임 | 설치 경로 |
| --- | --- |
| Claude Code | `~/.claude/skills/mingli-master/` |
| Codex CLI | `~/.codex/skills/mingli-master/` |
| Cursor | `~/.cursor/skills/mingli-master/` |

```bash
git clone https://github.com/learnwithu/mingli-master ~/.codex/skills/mingli-master/
```

### 방법 3: 프롬프트로 사용

런타임이 Agent Skills 자동 로딩을 지원하지 않아도 `SKILL.md` 내용을 대화에 붙여 넣어 사용할 수 있습니다. 이 저장소의 핵심은 Markdown 지침과 Python 보조 스크립트입니다.

---

## 사용

설치 후 자연어로 요청합니다.

```text
1991년 8월 15일, 축시, 남성 명반을 봐줘.
일과 돈 흐름을 중심으로 해석해줘.
올해 운세에서 조심할 지점을 봐줘.
손금 사진도 같이 보고 명반과 교차 검증해줘.
```

직접 스크립트를 실행할 수도 있습니다.

```bash
python3 scripts/calculate_chart.py --solar 1991-8-15 --hour 1 --gender 남 --output /tmp/chart.json
python3 scripts/generate_html.py --chart /tmp/chart.json --reading examples/musk_reading.ko.json --output public/index.html
```

---

## AI 기능 범위

이 저장소에는 두 가지 사용 방식이 있습니다.

**Agent Skill 방식**에서는 Claude Code, Codex 같은 외부 AI 에이전트가 `chart.json`과 `references/` 문서를 읽고 `reading.json` 해석문을 작성합니다. 이때 AI가 담당하는 일은 명반 계산이 아니라 해석 문장화, 상담식 설명, 보정 질문 작성입니다.

**웹앱 방식**의 [app.py](app.py)는 `Codex CLI`를 비대화 모드로 호출합니다. 생년월일시를 `iztro-py`로 계산한 뒤, 계산된 명반 JSON과 `SKILL.md`, `references/` 문서를 Codex CLI에 전달해 `reading.json`을 생성하고 HTML로 렌더링합니다.

현재 웹앱이 제공하는 기능:

- 양력/음력, 시진, 성별 입력
- 12궁, 주성, 보조성, 사화, 대운 계산
- Codex CLI 기반 한국어 명반 해석 생성
- 한국어 명반 HTML 보고서 저장
- 보정 질문 답변 제출 후 Codex CLI 재분석
- 최초 보고서와 보정 보고서 누적 저장
- 과거 보고서 목록과 개별 보고서 열람

아직 없는 기능:

- 손금 이미지 인식
- 채팅형 추가 질문 답변
- 긴 요청의 진행률 표시

보정 질문에 답하면 Codex CLI가 이전 해석과 답변을 함께 참고해 새 보고서를 작성합니다. 다만 결과가 보장되는 것은 아니며, 답변은 해석을 조정하는 추가 근거입니다.

---

## 작동 방식

입력 이후의 진행 과정은 네 단계입니다.

**1. 정확한 명반 계산**

`calculate_chart.py`가 `iztro-py`를 호출해 12궁, 별 배치, 사화, 대운을 계산합니다. 수학적 계산은 LLM이 아니라 Python이 처리하므로 생년월일시가 바뀌어도 일관된 결과를 냅니다.

**2. 한국어 해석 작성**

계산된 JSON을 바탕으로 14주성, 육길·육살, 사화 규칙을 참고해 한국어 해석을 만듭니다. 문체는 `references/interpretation_guide.md`의 기준을 따릅니다.

**3. 손금 교차 검증(선택)**

손금 사진이나 설명이 있으면 생명선, 지능선, 감정선의 특징을 뽑아 명반과 맞는 지점과 어긋나는 지점을 표시합니다.

**4. HTML 시각화**

명반 데이터와 해석 JSON을 `templates/chart_template.html`에 넣어 바로 배포 가능한 정적 HTML을 생성합니다.

---

## 저장소 구조

```text
mingli-master/
├── SKILL.md                          # 한국어 Agent Skill 본문
├── README.md                         # 프로젝트 안내
├── requirements.txt                  # Python 의존성
├── examples/
│   └── musk_reading.ko.json          # 배포 검증용 한국어 해석 예시
├── scripts/
│   ├── calculate_chart.py            # 명반 계산 스크립트
│   └── generate_html.py              # HTML 리포트 생성 스크립트
├── templates/
│   └── chart_template.html           # 한국어 HTML 템플릿
├── references/
│   ├── interpretation_guide.md       # 해석 문체 가이드
│   ├── stars_reference.md            # 14주성, 육길, 육살 참고
│   └── four_hua_reference.md         # 사화 참고
└── assets/
    └── musk-mingpan.jpg              # 예시 명반 이미지
```

---

## 왜 LLM이 직접 계산하지 않나?

자미두수 명반 계산은 정확한 규칙 계산입니다.

- 명궁 배치: 생월과 생시에 따라 정해짐
- 오행국 산정: 명궁 지지와 생년 천간에 따라 정해짐
- 14주성 배치: 오행국과 생일에 따라 정해짐
- 사화 배치: 생년 천간에 따라 정해짐

LLM이 기억만으로 계산하면 오행국이나 사화 순서를 틀릴 수 있습니다. 이 저장소는 계산을 Python에 맡기고, LLM은 해석과 문장화에 집중하도록 분리합니다.

---

## 감사

- [iztro](https://github.com/SylarLong/iztro): 자미두수 배반 JavaScript 라이브러리
- [iztro-py](https://github.com/spyfree/iztro-py): 순수 Python iztro 구현

---

## 라이선스

MIT

---

*명반은 가능성을 보여주고, 현실은 행동으로 결정됩니다.*
