#!/usr/bin/env python3
"""명반 HTML 생성 스크립트.

계산된 명반 JSON과 해석 JSON을 읽어 한국어 HTML 리포트를 생성합니다.

사용 예:
    python3 generate_html.py --chart chart_data.json --reading reading.json --output index.html
"""
import argparse
import json
import os

HOUR_NAMES_MAP = {
    0: '조자시', 1: '축시', 2: '인시', 3: '묘시',
    4: '진시', 5: '사시', 6: '오시', 7: '미시',
    8: '신시', 9: '유시', 10: '술시', 11: '해시', 12: '야자시',
}

# 4x4 명반 격자의 궁 배치입니다. 바깥 테두리를 시계 방향으로 배치합니다.
# 1행: 사, 오, 미, 신
# 2행: 진, 중앙, 중앙, 유
# 3행: 묘, 중앙, 중앙, 술
# 4행: 인, 축, 자, 해
GRID_ORDER = [
    {'index': None, 'row': 1, 'col': 1},
    {'index': None, 'row': 1, 'col': 2},
    {'index': None, 'row': 1, 'col': 3},
    {'index': None, 'row': 1, 'col': 4},
    {'index': None, 'row': 2, 'col': 1},
    {'index': None, 'row': 2, 'col': 4},
    {'index': None, 'row': 3, 'col': 1},
    {'index': None, 'row': 3, 'col': 4},
    {'index': None, 'row': 4, 'col': 1},
    {'index': None, 'row': 4, 'col': 2},
    {'index': None, 'row': 4, 'col': 3},
    {'index': None, 'row': 4, 'col': 4},
]

BRANCH_GRID_MAP = {
    '사': (1, 1), '오': (1, 2), '미': (1, 3), '신': (1, 4),
    '진': (2, 1),                          '유': (2, 4),
    '묘': (3, 1),                          '술': (3, 4),
    '인': (4, 1), '축': (4, 2), '자': (4, 3), '해': (4, 4),
}


def build_palace_cell(palace, soul_branch, body_branch, current_decadal_branch):
    branch = palace['earthly_branch']
    name = palace['name']
    major = palace['major_stars']
    minor = palace['minor_stars']
    mutagens = palace['mutagens']

    classes = ['palace']
    if branch == soul_branch:
        classes.append('active')
    if branch == current_decadal_branch:
        classes.append('current-limit')

    stars_html = ''
    if major:
        for star in major:
            mutagen = next((m['mutagen'] for m in mutagens if m['star'] == star), None)
            stars_html += f'<span class="star main">{star}</span>\n'
            if mutagen:
                stars_html += f'<span class="star four-hua">{star}{mutagen}</span>\n'
        for star in minor:
            mutagen = next((m['mutagen'] for m in mutagens if m['star'] == star), None)
            stars_html += f'<span class="star">{star}</span>\n'
            if mutagen:
                stars_html += f'<span class="star four-hua">{star}{mutagen}★</span>\n'
    else:
        stars_html = '<span class="star empty">공궁</span>\n'

    badges = ''
    for tag in palace['tags']:
        if tag == '명궁':
            badges += '<div class="palace-badge badge-ming">명궁</div>\n'
        elif tag == '신궁':
            badges += '<div class="palace-badge badge-body">신궁</div>\n'

    if branch == current_decadal_branch and '명궁' not in palace['tags'] and '신궁' not in palace['tags']:
        badges += '<div class="palace-badge badge-limit">현재 대운</div>\n'

    return f'''<div class="{' '.join(classes)}">
      <div class="palace-name">{name}</div>
      <div class="palace-dizhi">{branch}</div>
      <div class="palace-stars">{stars_html}</div>
      {badges}
    </div>'''


def build_palace_grid(palaces, soul_branch, body_branch, current_decadal_branch):
    grid = {}
    for palace in palaces:
        branch = palace['earthly_branch']
        if branch in BRANCH_GRID_MAP:
            row, col = BRANCH_GRID_MAP[branch]
            grid[(row, col)] = build_palace_cell(
                palace,
                soul_branch,
                body_branch,
                current_decadal_branch,
            )

    cells = []
    for row in range(1, 5):
        for col in range(1, 5):
            if row in (2, 3) and col in (2, 3):
                continue
            cells.append(grid.get((row, col), '<div class="palace"></div>'))

    return '\n    '.join(cells)


def build_four_hua_tags(year_mutagens):
    mutagen_classes = {
        '화록': 'hua-lu', '화권': 'hua-quan',
        '화과': 'hua-ke', '화기': 'hua-ji',
    }
    tags = []
    for mutagen in year_mutagens:
        css_class = mutagen_classes.get(mutagen['mutagen'], '')
        tags.append(f'<span class="hua-tag {css_class}">{mutagen["star"]}{mutagen["mutagen"]}</span>')
    return '\n        '.join(tags)


def build_reading_cards(reading):
    nums = ['하나', '둘', '셋', '넷', '다섯', '여섯', '일곱']
    cards = []
    for index, card in enumerate(reading.get('cards', [])):
        num = nums[index] if index < len(nums) else str(index + 1)
        classes = ['reading-card']
        if card.get('full'):
            classes.append('full')
        if card.get('highlight'):
            classes.append('highlight')
        if card.get('teal'):
            classes.append('teal-highlight')

        probability_html = ''
        if card.get('probabilities'):
            for probability in card['probabilities']:
                probability_html += f'''<div class="prob-bar">
                    <span class="prob-label">{probability['label']}</span>
                    <div class="prob-track"><div class="prob-fill" style="width:{probability['pct']}%"></div></div>
                    <span class="prob-pct">{probability['pct']}%</span>
                </div>\n'''

        cards.append(f'''<div class="{' '.join(classes)}" data-num="{num}">
      <div class="card-title">{card['title']}</div>
      <div class="card-stars-badge">{card.get('badge', '')}</div>
      <div class="card-body">{card['body']}</div>
      {f'<div style="margin-top:16px;">{probability_html}</div>' if probability_html else ''}
    </div>''')

    return '\n    '.join(cards)


def build_hand_section(hand_data):
    if not hand_data or not hand_data.get('items'):
        return ''

    cards_html = ''
    for item in hand_data['items']:
        status_tag = ''
        if item.get('status') == 'match':
            status_tag = f'<div class="conflict-tag match">{item["status_text"]}</div>'
        elif item.get('status') == 'conflict':
            status_tag = f'<div class="conflict-tag conflict">{item["status_text"]}</div>'
            if item.get('resolution'):
                status_tag += (
                    '<div style="font-size:11px;color:var(--ivory-dim);'
                    f'margin-top:6px;line-height:1.7;">판단 기준: {item["resolution"]}</div>'
                )

        cards_html += f'''<div class="hand-card">
        <div class="hand-card-title">{item['title']}</div>
        <div class="hand-card-body">{item['body']}</div>
        {status_tag}
      </div>\n'''

    return f'''<div class="section-title">손금 교차 검증</div>
  <div class="hand-section">
    <div class="hand-grid">{cards_html}</div>
  </div>'''


def build_calibration(questions):
    nums = ['하나', '둘', '셋', '넷', '다섯']
    html = ''
    for index, question in enumerate(questions[:5]):
        num = nums[index] if index < len(nums) else str(index + 1)
        hint = f'<span>{question["hint"]}</span>' if question.get('hint') else ''
        html += f'''<div class="cal-q">
        <div class="cal-num">{num}</div>
        <div class="cal-field">
          <div class="cal-text">{question['text']}{hint}</div>
          <textarea class="cal-answer" name="calibration_{index + 1}" rows="3" placeholder="답변을 적어 두세요. 이 내용은 재해석할 때 보정 근거로 사용합니다."></textarea>
        </div>
      </div>\n'''
    return html


def generate_html(chart_data, reading_data, template_path):
    with open(template_path, 'r', encoding='utf-8') as template_file:
        template = template_file.read()

    soul_branch = chart_data['soul_palace_branch']
    body_branch = chart_data['body_palace_branch']

    soul_palace = next((p for p in chart_data['palaces'] if '명궁' in p.get('tags', [])), None)
    soul_stars = (
        '·'.join(soul_palace['major_stars'])
        if soul_palace and soul_palace['major_stars']
        else '공궁(대궁 별 차용)'
    )

    hour_name = HOUR_NAMES_MAP.get(chart_data['hour_index'], '축시')
    current_decadal_branch = reading_data.get('current_decadal_branch', '')

    palace_cells = build_palace_grid(
        chart_data['palaces'],
        soul_branch,
        body_branch,
        current_decadal_branch,
    )
    four_hua_tags = build_four_hua_tags(chart_data['year_mutagens'])
    reading_cards = build_reading_cards(reading_data)
    hand_section = build_hand_section(reading_data.get('hand_reading'))
    calibration = build_calibration(reading_data.get('calibration_questions', []))

    solar = chart_data.get('solar_date', '')
    lunar = chart_data.get('lunar_date', '')
    chinese = chart_data.get('chinese_date', '')

    parts = chinese.split() if chinese else []
    year_sb = parts[0] if parts else ''
    year_stem_char = year_sb[0] if len(year_sb) >= 2 else ''
    year_branch_char = year_sb[1] if len(year_sb) >= 2 else ''

    date_info = f'양력 {solar}' if solar else ''
    lunar_info = f'음력 {lunar}' if lunar else ''

    replacements = {
        '{{YEAR_STEM}}': year_stem_char,
        '{{YEAR_BRANCH}}': year_branch_char,
        '{{HOUR_NAME}}': hour_name,
        '{{LUNAR_DATE}}': lunar,
        '{{GENDER}}': chart_data['gender'],
        '{{FIVE_ELEMENTS}}': chart_data['five_elements'],
        '{{SOUL_PALACE_BRANCH}}': soul_branch,
        '{{SOUL_PALACE_STARS}}': soul_stars,
        '{{CURRENT_DECADAL}}': reading_data.get('current_decadal_display', ''),
        '{{PALACE_CELLS}}': palace_cells,
        '{{FOUR_HUA_TAGS}}': four_hua_tags,
        '{{DATE_INFO}}': date_info,
        '{{LUNAR_INFO}}': lunar_info,
        '{{READING_CARDS}}': reading_cards,
        '{{HAND_SECTION}}': hand_section,
        '{{CALIBRATION_QUESTIONS}}': calibration,
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, str(value))

    return html


def main():
    parser = argparse.ArgumentParser(description='명반 HTML 생성')
    parser.add_argument('--chart', required=True, help='명반 데이터 JSON 파일')
    parser.add_argument('--reading', required=True, help='해석 데이터 JSON 파일')
    parser.add_argument('--template', help='HTML 템플릿 경로(기본값: 내장 템플릿)')
    parser.add_argument('--output', required=True, help='출력 HTML 파일 경로')

    args = parser.parse_args()

    with open(args.chart, 'r', encoding='utf-8') as chart_file:
        chart_data = json.load(chart_file)

    with open(args.reading, 'r', encoding='utf-8') as reading_file:
        reading_data = json.load(reading_file)

    template_path = args.template
    if not template_path:
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'chart_template.html')
        template_path = os.path.abspath(template_path)

    html = generate_html(chart_data, reading_data, template_path)

    with open(args.output, 'w', encoding='utf-8') as output_file:
        output_file.write(html)

    print(f'명반 HTML 생성 완료: {args.output}')


if __name__ == '__main__':
    main()
