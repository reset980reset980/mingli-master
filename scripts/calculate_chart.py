#!/usr/bin/env python3
"""자미두수 명반 계산 스크립트.

iztro-py로 생년월일시를 계산해 12궁, 주요 별, 사화, 대운 데이터를 JSON으로
내보냅니다. 화면 표시용 명칭은 한국어로 정리합니다.

사용 예:
    python3 calculate_chart.py --solar 1991-8-15 --hour 1 --gender 남
    python3 calculate_chart.py --lunar 1991-7-6 --hour 1 --gender 남 --leap
"""
import argparse
import json
import re

BRANCH_KO = {
    'ziEarthly': '자', 'chouEarthly': '축', 'yinEarthly': '인',
    'maoEarthly': '묘', 'chenEarthly': '진', 'siEarthly': '사',
    'wuEarthly': '오', 'weiEarthly': '미', 'shenEarthly': '신',
    'youEarthly': '유', 'xuEarthly': '술', 'haiEarthly': '해',
    '子': '자', '丑': '축', '寅': '인', '卯': '묘', '辰': '진', '巳': '사',
    '午': '오', '未': '미', '申': '신', '酉': '유', '戌': '술', '亥': '해',
}

STEM_KO = {
    'jiaHeavenly': '갑', 'yiHeavenly': '을', 'bingHeavenly': '병',
    'dingHeavenly': '정', 'wuHeavenly': '무', 'jiHeavenly': '기',
    'gengHeavenly': '경', 'xinHeavenly': '신', 'renHeavenly': '임',
    'guiHeavenly': '계',
    '甲': '갑', '乙': '을', '丙': '병', '丁': '정', '戊': '무',
    '己': '기', '庚': '경', '辛': '신', '壬': '임', '癸': '계',
}

FIVE_ELEMENTS_KO = {
    'water2': '수 2국', 'wood3': '목 3국', 'metal4': '금 4국',
    'earth5': '토 5국', 'fire6': '화 6국',
    '水二局': '수 2국', '木三局': '목 3국', '金四局': '금 4국',
    '土五局': '토 5국', '火六局': '화 6국',
}

MUTAGEN_KO = {
    '禄': '화록', '权': '화권', '科': '화과', '忌': '화기',
    '化禄': '화록', '化权': '화권', '化科': '화과', '化忌': '화기',
}

DISPLAY_NAME_KO = {
    '命宫': '명궁', '兄弟': '형제궁', '兄弟宫': '형제궁', '夫妻': '부부궁',
    '夫妻宫': '부부궁', '子女': '자녀궁', '子女宫': '자녀궁', '财帛': '재백궁',
    '财帛宫': '재백궁', '疾厄': '질액궁', '疾厄宫': '질액궁', '迁移': '천이궁',
    '迁移宫': '천이궁', '仆役': '교우궁', '仆役宫': '교우궁', '交友': '교우궁',
    '交友宫': '교우궁', '官禄': '관록궁', '官禄宫': '관록궁', '田宅': '전택궁',
    '田宅宫': '전택궁', '福德': '복덕궁', '福德宫': '복덕궁', '父母': '부모궁',
    '父母宫': '부모궁',
    '紫微': '자미', '天机': '천기', '太阳': '태양', '武曲': '무곡', '天同': '천동',
    '廉贞': '염정', '天府': '천부', '太阴': '태음', '贪狼': '탐랑', '巨门': '거문',
    '天相': '천상', '天梁': '천량', '七杀': '칠살', '破军': '파군',
    '左辅': '좌보', '右弼': '우필', '文昌': '문창', '文曲': '문곡',
    '天魁': '천괴', '天钺': '천월', '禄存': '녹존', '擎羊': '경양',
    '陀罗': '타라', '火星': '화성', '铃星': '영성', '地空': '지공',
    '地劫': '지겁', '天马': '천마', '红鸾': '홍란', '天喜': '천희',
    '天刑': '천형', '天姚': '천요', '解神': '해신', '天巫': '천무',
    '天月': '천월', '阴煞': '음살', '台辅': '태보', '封诰': '봉고',
    '三台': '삼태', '八座': '팔좌', '恩光': '은광', '天贵': '천귀',
    '龙池': '용지', '凤阁': '봉각', '孤辰': '고진', '寡宿': '과숙',
    '蜚廉': '비렴', '破碎': '파쇄', '天空': '천공', '天才': '천재',
    '天寿': '천수', '天官': '천관', '天福': '천복', '天哭': '천곡',
    '天虚': '천허', '天使': '천사', '天伤': '천상', '截空': '절공',
    '旬空': '순공', '大耗': '대모', '小耗': '소모', '咸池': '함지',
    '月德': '월덕', '天德': '천덕', '岁建': '세건', '晦气': '회기',
    '丧门': '상문', '贯索': '관삭', '官符': '관부', '小耗': '소모',
    '大耗': '대모', '龙德': '용덕', '白虎': '백호', '天德': '천덕',
    '吊客': '조객', '病符': '병부',
}

GENDER_TO_ASTRO = {
    '남': '男', '남자': '男', '男': '男',
    '여': '女', '여자': '女', '女': '女',
}

GENDER_DISPLAY = {'男': '남성', '女': '여성'}

LUNAR_CHAR_KO = {
    '〇': '0', '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
    '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
    '十': '10', '年': '년 ', '月': '월 ', '日': '일', '初': '초',
    '闰': '윤', '正': '1', '冬': '11', '腊': '12',
}

GANZHI_KO = {
    '甲': '갑', '乙': '을', '丙': '병', '丁': '정', '戊': '무',
    '己': '기', '庚': '경', '辛': '신', '壬': '임', '癸': '계',
    '子': '자', '丑': '축', '寅': '인', '卯': '묘', '辰': '진',
    '巳': '사', '午': '오', '未': '미', '申': '신', '酉': '유',
    '戌': '술', '亥': '해',
}


def translate_name(obj):
    """iztro 객체나 문자열을 화면용 한국어 명칭으로 변환합니다."""
    if hasattr(obj, 'translate_name'):
        raw = obj.translate_name()
    else:
        raw = str(obj)
    return DISPLAY_NAME_KO.get(raw, raw)


def normalize_gender(gender):
    normalized = GENDER_TO_ASTRO.get(gender)
    if not normalized:
        raise ValueError('성별은 남, 여, 男, 女 중 하나로 입력하세요.')
    return normalized


def translate_lunar_date(text):
    """중국식 음력 문자열을 한국어 표시 문자열로 정리합니다."""
    if not text:
        return text

    def year_digits(raw):
        return ''.join(LUNAR_CHAR_KO.get(char, char) for char in raw)

    def cn_number(raw):
        special = {'正': 1, '冬': 11, '腊': 12}
        digits = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        if raw in special:
            return special[raw]
        if raw == '十':
            return 10
        if raw.startswith('十'):
            return 10 + digits.get(raw[-1], 0)
        if raw.startswith('廿'):
            return 20 + (digits.get(raw[-1], 0) if len(raw) > 1 else 0)
        if raw.startswith('卅'):
            return 30 + (digits.get(raw[-1], 0) if len(raw) > 1 else 0)
        if '十' in raw:
            left, right = raw.split('十', 1)
            return digits.get(left, 0) * 10 + (digits.get(right, 0) if right else 0)
        return digits.get(raw, raw)

    match = re.match(
        r'(?P<year>[〇零一二三四五六七八九]+)年(?P<leap>闰?)(?P<month>正|冬|腊|[一二三四五六七八九十]+)月(?P<day>初?[一二三四五六七八九十]|十[一二三四五六七八九]?|廿[一二三四五六七八九]?|三十|卅)',
        text,
    )
    if match:
        year = year_digits(match.group('year'))
        leap = '윤' if match.group('leap') else ''
        month = cn_number(match.group('month'))
        day_raw = match.group('day')
        day_prefix = '초' if day_raw.startswith('初') else ''
        day = cn_number(day_raw.replace('初', ''))
        return f'{year}년 {leap}{month}월 {day_prefix}{day}일'

    translated = ''.join(LUNAR_CHAR_KO.get(char, char) for char in text)
    return ' '.join(translated.split())


def translate_ganzhi_text(text):
    """간지 문자열을 한국어 음으로 변환합니다."""
    if not text:
        return text
    return ''.join(GANZHI_KO.get(char, char) for char in text)


def build_chart(date_str, hour_index, gender, is_lunar=False, is_leap=False, language='zh-CN'):
    from iztro_py import astro

    astro_gender = normalize_gender(gender)
    if is_lunar:
        chart = astro.by_lunar(date_str, hour_index, astro_gender, is_leap, True, language)
    else:
        chart = astro.by_solar(date_str, hour_index, astro_gender, language)

    soul_idx = chart.get_soul_palace().index
    body_idx = chart.get_body_palace().index

    five_elements = FIVE_ELEMENTS_KO.get(chart.five_elements_class, chart.five_elements_class)

    # 생년 사화는 명반의 핵심 흐름이므로 별, 사화, 궁, 지지를 함께 저장합니다.
    year_mutagens = []
    for palace in chart.palaces:
        for star in list(palace.major_stars) + list(palace.minor_stars):
            if hasattr(star, 'mutagen') and star.mutagen:
                year_mutagens.append({
                    'star': translate_name(star),
                    'mutagen': MUTAGEN_KO.get(star.mutagen, star.mutagen),
                    'palace': translate_name(palace),
                    'branch': BRANCH_KO.get(palace.earthly_branch, palace.earthly_branch),
                })

    # 12궁의 표시 데이터를 HTML 템플릿에서 바로 사용할 수 있는 형태로 정리합니다.
    palaces = []
    for palace in chart.palaces:
        major = [translate_name(star) for star in palace.major_stars]
        minor = [translate_name(star) for star in palace.minor_stars]
        adjective = [
            translate_name(star)
            for star in palace.adjective_stars
        ] if hasattr(palace, 'adjective_stars') else []

        star_mutagens = []
        for star in list(palace.major_stars) + list(palace.minor_stars):
            if hasattr(star, 'mutagen') and star.mutagen:
                star_mutagens.append({
                    'star': translate_name(star),
                    'mutagen': MUTAGEN_KO.get(star.mutagen, star.mutagen),
                })

        decadal = palace.decadal
        decadal_range = f"{decadal.range[0]}-{decadal.range[1]}" if decadal else ""
        decadal_stem = STEM_KO.get(decadal.heavenly_stem, decadal.heavenly_stem) if decadal else ""
        decadal_branch = BRANCH_KO.get(decadal.earthly_branch, decadal.earthly_branch) if decadal else ""
        heavenly_stem = STEM_KO.get(palace.heavenly_stem, palace.heavenly_stem)
        earthly_branch = BRANCH_KO.get(palace.earthly_branch, palace.earthly_branch)

        tags = []
        if palace.index == soul_idx:
            tags.append('명궁')
        if palace.index == body_idx:
            tags.append('신궁')

        palaces.append({
            'name': translate_name(palace),
            'heavenly_stem': heavenly_stem,
            'earthly_branch': earthly_branch,
            'dizhi': heavenly_stem + earthly_branch,
            'major_stars': major,
            'minor_stars': minor,
            'adjective_stars': adjective[:5],
            'mutagens': star_mutagens,
            'is_empty': not major,
            'decadal_range': decadal_range,
            'decadal_dizhi': decadal_stem + decadal_branch,
            'tags': tags,
            'index': palace.index,
        })

    # 주성이 없는 궁은 별도로 표시해 해석 단계에서 대궁을 빌려 보도록 안내합니다.
    empty_palaces_result = chart.empty_palaces() if callable(getattr(chart, 'empty_palaces', None)) else []
    empty_palaces = [
        BRANCH_KO.get(empty_palace.earthly_branch, str(empty_palace))
        for empty_palace in empty_palaces_result
    ]

    return {
        'solar_date': date_str if not is_lunar else None,
        'lunar_date': date_str if is_lunar else translate_lunar_date(chart.lunar_date),
        'chinese_date': translate_ganzhi_text(chart.chinese_date),
        'gender': GENDER_DISPLAY[astro_gender],
        'hour_index': hour_index,
        'five_elements': five_elements,
        'soul_palace_branch': BRANCH_KO.get(
            chart.earthly_branch_of_soul_palace,
            chart.earthly_branch_of_soul_palace,
        ),
        'body_palace_branch': BRANCH_KO.get(
            chart.earthly_branch_of_body_palace,
            chart.earthly_branch_of_body_palace,
        ),
        'year_mutagens': year_mutagens,
        'empty_palaces': empty_palaces,
        'palaces': palaces,
    }


HOUR_NAMES = {
    0: '조자시 (23:00-00:00)', 1: '축시 (01:00-03:00)',
    2: '인시 (03:00-05:00)', 3: '묘시 (05:00-07:00)',
    4: '진시 (07:00-09:00)', 5: '사시 (09:00-11:00)',
    6: '오시 (11:00-13:00)', 7: '미시 (13:00-15:00)',
    8: '신시 (15:00-17:00)', 9: '유시 (17:00-19:00)',
    10: '술시 (19:00-21:00)', 11: '해시 (21:00-23:00)',
    12: '야자시 (23:00-00:00)',
}


def main():
    parser = argparse.ArgumentParser(description='자미두수 명반 계산')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--solar', help='양력 날짜, 형식 YYYY-M-D')
    group.add_argument('--lunar', help='음력 날짜, 형식 YYYY-M-D')
    parser.add_argument(
        '--hour',
        type=int,
        required=True,
        help='시진 번호: 0=조자 1=축 2=인 ... 11=해 12=야자',
    )
    parser.add_argument('--gender', required=True, choices=['남', '여', '남자', '여자', '男', '女'])
    parser.add_argument('--leap', action='store_true', help='음력 윤달 여부(--lunar일 때만 사용)')
    parser.add_argument('--output', help='출력 파일 경로(기본값: stdout)')

    args = parser.parse_args()

    is_lunar = args.lunar is not None
    date_str = args.lunar if is_lunar else args.solar
    chart = build_chart(date_str, args.hour, args.gender, is_lunar, args.leap)

    output = json.dumps(chart, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as output_file:
            output_file.write(output)
        print(f'명반 데이터 저장 완료: {args.output}')
    else:
        print(output)


if __name__ == '__main__':
    main()
