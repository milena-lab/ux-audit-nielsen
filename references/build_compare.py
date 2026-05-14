#!/usr/bin/env python3
"""
build_compare.py — собирает HTML-артефакт сравнительного UX-аудита.

Использование:
  python3 build_compare.py \\
    --data /tmp/compare-data.json \\
    --template references/html-template-compare.html \\
    --output /mnt/user-data/outputs/ux-compare-NAME.html

Структура JSON (compare-data.json):
{
  "title": "UX-сравнение: Концепт 1 vs Концепт 2",
  "meta": "Авито · кабинет продавца · параллельное сравнение",
  "concepts": [
    {
      "screenshot_path": "/mnt/user-data/uploads/c1.jpg",
      "caption": "Концепт 1",
      "subcaption": "Плоская подача...",
      "strengths": ["Чище визуально", "..."]
    },
    {
      "screenshot_path": "/mnt/user-data/uploads/c2.jpg",
      "caption": "Концепт 2",
      "subcaption": "Сценарная структура...",
      "strengths": ["Лучше UX...", "..."]
    }
  ],
  "no_screenshots": false,
  "top_conclusion": "Концепт 2 явно сильнее...",
  "rows": [
    {
      "type_icon": "🤔",
      "type_label": "Непонятно",
      "heuristic": "1. Видимость статуса",
      "comparison": "winner_2",
      "problem": "В Концепте 1 пользователь может...",
      "risk": "Снижение вовлечения",
      "criticality": "🟠 Средняя",
      "action": "..."
    }
  ],
  "hybrid_recommendation": "Взять структуру Концепта 2..."
}

Значения "comparison": "winner_1", "winner_2", "winner_3", "winner_4", "tie"
Значения "criticality": "🔴 Высокая", "🟠 Средняя", "🟡 Низкая", "🟢 Нулевая"

Скрипт сам:
- Уменьшает скриншоты до 1100 px, JPEG 82%, base64
- Подсчитывает score каждого концепта по формуле
- Выделяет победителя зелёным цветом в шапке
- Собирает блоки сильных сторон
- Добавляет дисклеймер про base64
"""

import argparse
import base64
import html
import json
import re
import sys
from io import BytesIO
from pathlib import Path


def encode_screenshot(path, max_width=1100, quality=82):
    try:
        from PIL import Image
    except ImportError:
        print("Установи Pillow: pip install Pillow --break-system-packages", file=sys.stderr)
        sys.exit(1)
    img = Image.open(path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode('ascii')


CRITICALITY_POINTS = {
    '🟢': 10, '🟡': 7, '🟠': 3, '🔴': 0,
}


def get_points(criticality_str):
    """🟠 Средняя -> 3"""
    if not criticality_str:
        return 10
    icon = criticality_str.split()[0] if criticality_str else '🟢'
    return CRITICALITY_POINTS.get(icon, 10)


def compute_scores(rows, concepts_count):
    """
    Считает % для каждого концепта.

    Новая методика (приоритетная, если есть `criticalities` в строке):
    - Каждый концепт оценивается независимо по каждой эвристике
    - У каждого своя критичность → каждый получает баллы по своей критичности
    - Это гарантирует, что оценка концепта в сравнении совпадает с оценкой того же
      концепта в одиночном аудите

    Старая методика (fallback для совместимости со старыми JSON без `criticalities`):
    - "tie" — оба получают баллы по общей критичности
    - "winner_N" — концепт N получает 10 (нет проблемы у него), остальные — по критичности
    """
    scores = [0] * concepts_count
    for row in rows:
        crits = row.get('criticalities')
        if crits and len(crits) == concepts_count:
            # Новая методика: каждый концепт по своей критичности
            for i in range(concepts_count):
                scores[i] += get_points(crits[i])
        else:
            # Старая методика (backwards compatibility)
            crit_points = get_points(row.get('criticality', '🟢 Нулевая'))
            comparison = row.get('comparison', 'tie')
            if comparison == 'tie':
                for i in range(concepts_count):
                    scores[i] += crit_points
            elif comparison.startswith('winner_'):
                winner_idx = int(comparison.split('_')[1]) - 1
                for i in range(concepts_count):
                    scores[i] += 10 if i == winner_idx else crit_points
    return scores


def determine_comparison(criticalities):
    """Автоматически выводит метку 'comparison' из массива криcтичностей.

    - Все одинаковые → 'tie'
    - Один явно лучше (больше баллов) → 'winner_N'
    - Несколько одинаково лучших → 'tie' (нет одного победителя)
    """
    points = [get_points(c) for c in criticalities]
    max_pts = max(points)
    winners = [i for i, p in enumerate(points) if p == max_pts]
    if len(winners) == 1:
        return f'winner_{winners[0] + 1}'
    return 'tie'


def derive_display_criticality(criticalities):
    """Возвращает критичность для отображения в колонке 'Критичность'.

    Берётся худшая (самая критичная) из массива — это та проблема, которую решает
    концепт-победитель. Если все одинаковые — возвращает её.
    """
    if not criticalities:
        return '🟢 Нулевая'
    worst = min(criticalities, key=get_points)
    return worst


def count_wins(rows, concepts_count):
    """Возвращает (wins_per_concept, ties)."""
    wins = [0] * concepts_count
    ties = 0
    for row in rows:
        crits = row.get('criticalities')
        if crits and len(crits) == concepts_count:
            comparison = row.get('comparison') or determine_comparison(crits)
        else:
            comparison = row.get('comparison', 'tie')
        if comparison == 'tie':
            ties += 1
        elif comparison.startswith('winner_'):
            idx = int(comparison.split('_')[1]) - 1
            if 0 <= idx < concepts_count:
                wins[idx] += 1
    return wins, ties


def build_screens_html(concepts, no_screenshots):
    cards = []
    for c in concepts:
        caption = html.escape(c.get('caption', 'Концепт'))
        subcaption = html.escape(c.get('subcaption', ''))
        subcaption_html = f'<div class="subcaption">{subcaption}</div>' if subcaption else ''
        path = c.get('screenshot_path')
        if no_screenshots or not path:
            cards.append(
                f'<div class="screen-textonly">'
                f'<div class="caption">{caption}</div>'
                f'{subcaption_html}'
                f'</div>'
            )
        else:
            b64 = encode_screenshot(path)
            cards.append(
                f'<a class="screen-card" href="data:image/jpeg;base64,{b64}" target="_blank">'
                f'<img src="data:image/jpeg;base64,{b64}" alt="{caption}">'
                f'<div class="caption">{caption}</div>'
                f'{subcaption_html}'
                f'</a>'
            )
    return '\n      '.join(cards)


def build_scores_html(concepts, scores, winner_idx):
    """Блоки с оценками для верхней плашки."""
    blocks = []
    for i, c in enumerate(concepts):
        winner_class = ' winner' if i == winner_idx else ''
        label = html.escape(c.get('caption', f'Концепт {i+1}'))
        blocks.append(
            f'<div class="score-block{winner_class}">'
            f'<span class="label">{label}</span>'
            f'<span class="value">{scores[i]}%</span>'
            f'</div>'
        )
    return '\n      '.join(blocks)


def build_row(row):
    type_icon = html.escape(row.get('type_icon', '✨'))
    type_label = html.escape(row.get('type_label', 'Всё хорошо'))
    heuristic = html.escape(row.get('heuristic', ''))
    problem = html.escape(row.get('problem', ''))
    risk = html.escape(row.get('risk', '—'))
    action = html.escape(row.get('action', '—'))

    # Если есть criticalities (массив) — выводим всё из него
    crits = row.get('criticalities')
    if crits and len(crits) >= 2:
        comparison = row.get('comparison') or determine_comparison(crits)
        criticality_display = row.get('criticality') or derive_display_criticality(crits)
    else:
        # Backwards compatibility со старым форматом
        comparison = row.get('comparison', 'tie')
        criticality_display = row.get('criticality', '🟢 Нулевая')

    criticality = html.escape(criticality_display)

    if comparison.startswith('winner_'):
        idx = comparison.split('_')[1]
        # Градация по критичности проблемы у проигравшего концепта:
        # 🔴 / 🟠 → насыщенный цвет (strong)
        # 🟡 → бледный цвет (soft)
        # Текст одинаковый, степень считывается визуально через цвет
        if criticality_display.startswith('🔴') or criticality_display.startswith('🟠'):
            strength_class = 'strong'
        else:
            strength_class = 'soft'
        cmp_html = f'<span class="cmp-{idx} {strength_class}">✓ Концепт {idx}</span>'
    else:
        cmp_html = '<span class="cmp-tie">⚖ Паритет</span>'

    klass = ' class="good"' if criticality_display.startswith('🟢') else ''
    return (
        f'        <tr{klass}>'
        f'<td><span class="icon">{type_icon}</span> {type_label}</td>'
        f'<td>{heuristic}</td>'
        f'<td>{cmp_html}</td>'
        f'<td>{problem}</td>'
        f'<td>{risk}</td>'
        f'<td>{criticality}</td>'
        f'<td>{action}</td>'
        f'</tr>'
    )


def build_strengths_html(concepts, scores):
    blocks = []
    for i, c in enumerate(concepts):
        caption = html.escape(c.get('caption', f'Концепт {i+1}'))
        score = scores[i]
        strengths = c.get('strengths', [])
        items_html = '\n        '.join(f'<li>{html.escape(s)}</li>' for s in strengths) or '<li>Не указаны</li>'
        blocks.append(
            f'<div class="strength-card c{i+1}">'
            f'<h3>{caption} <span class="strength-score">{score}%</span></h3>'
            f'<ul>{items_html}</ul>'
            f'</div>'
        )
    return '\n    '.join(blocks)


def build_hybrid_html(data):
    rec = data.get('hybrid_recommendation', '').strip()
    if not rec:
        return ''
    return (
        '<div class="hybrid">'
        '<h3>Рекомендация — гибрид</h3>'
        f'<p>{html.escape(rec)}</p>'
        '</div>'
    )


def build_disclaimer_html(data):
    has_screens = any(c.get('screenshot_path') for c in data.get('concepts', []))
    if has_screens and not data.get('no_screenshots'):
        return (
            '<div class="disclaimer">'
            'Артефакт содержит встроенные скриншоты в base64. '
            'Учитывай при пересылке — скрины «уезжают» вместе с файлом.'
            '</div>'
        )
    return ''


def validate_top_conclusion(top_conclusion, scores):
    """
    Проверяет, что проценты в top_conclusion совпадают с реальными оценками.

    Если в тексте есть числа в формате "N%" в диапазоне 40-100 (правдоподобные
    оценки концептов), которые не совпадают ни с одной из реально посчитанных
    оценок — возвращает список таких чисел. Иначе — пустой список.

    Это защита от того, что аудитор написал вывод вручную ДО прогона скрипта
    (или забыл обновить после правки criticalities), и автоподсчёт оценок
    разошёлся с текстом-выводом.
    """
    if not top_conclusion:
        return []
    # Ищем все вхождения вида "84%", "84 %", "84&nbsp;%"
    percentages = [int(m) for m in re.findall(r'(\d{1,3})\s*%', top_conclusion)]
    if not percentages:
        return []
    real_scores_set = set(scores)
    # Возвращаем только те числа, которые попадают в правдоподобный
    # диапазон оценок (40-100), но не совпадают с реальными
    mismatched = [p for p in percentages if 40 <= p <= 100 and p not in real_scores_set]
    return mismatched


def main():
    ap = argparse.ArgumentParser(description='Сборщик HTML-артефакта UX-сравнения.')
    ap.add_argument('--data', required=True)
    ap.add_argument('--template', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    template = Path(args.template).read_text(encoding='utf-8')

    concepts = data.get('concepts', [])
    n = len(concepts)
    if n < 2:
        print('Ошибка: для сравнения нужно минимум 2 концепта', file=sys.stderr)
        sys.exit(1)
    if n > 4:
        print(f'Предупреждение: концептов {n} (>4) — макет может быть некомфортным', file=sys.stderr)

    rows = data.get('rows', [])
    scores = compute_scores(rows, n)
    winner_idx = scores.index(max(scores)) if len(set(scores)) > 1 else -1

    # Валидация: проверяем, что проценты в top_conclusion не противоречат
    # автоматически посчитанным оценкам концептов
    top_conclusion = data.get('top_conclusion', '')
    mismatched = validate_top_conclusion(top_conclusion, scores)
    if mismatched:
        real_str = ', '.join(f'{s}%' for s in scores)
        mismatched_str = ', '.join(f'{m}%' for m in mismatched)
        print('', file=sys.stderr)
        print('⚠️  ВНИМАНИЕ: расхождение между текстом и автоподсчётом', file=sys.stderr)
        print(f'   В top_conclusion упомянуты: {mismatched_str}', file=sys.stderr)
        print(f'   Скрипт посчитал реальные оценки: {real_str}', file=sys.stderr)
        print(f'   Возможно, текст вывода устарел или написан до правки criticalities.', file=sys.stderr)
        print(f'   Обновите формулировку в JSON, чтобы числа сошлись.', file=sys.stderr)
        print('', file=sys.stderr)

    replacements = {
        '{{TITLE}}': html.escape(data.get('title', 'UX-сравнение')),
        '{{META}}': html.escape(data.get('meta', '')),
        '{{TOP_CONCLUSION}}': data.get('top_conclusion', '').replace('<', '&lt;').replace('>', '&gt;'),
        # top_conclusion может содержать <strong> — оставим разметку. Экранируем только опасные символы.
        # Если нужны теги в conclusion — передавай уже готовый HTML в этом поле.
        '{{SCREENS_HTML}}': build_screens_html(concepts, data.get('no_screenshots', False)),
        '{{SCORES_HTML}}': build_scores_html(concepts, scores, winner_idx),
        '{{ROWS_HTML}}': '\n'.join(build_row(r) for r in rows),
        '{{STRENGTHS_HTML}}': build_strengths_html(concepts, scores),
        '{{HYBRID_HTML}}': build_hybrid_html(data),
        '{{DISCLAIMER_HTML}}': build_disclaimer_html(data),
        '{{CONCEPTS_COUNT}}': str(n),
    }

    # Топ-conclusion позволяет HTML-теги (для <strong>), поэтому отдельная обработка
    replacements['{{TOP_CONCLUSION}}'] = data.get('top_conclusion', '')

    html_out = template
    for placeholder, value in replacements.items():
        html_out = html_out.replace(placeholder, value)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding='utf-8')

    size_kb = out_path.stat().st_size / 1024
    wins, ties = count_wins(rows, n)
    print(f'OK: {out_path} ({size_kb:.1f} КБ)')
    print(f'   Оценки: {", ".join(f"К{i+1}={scores[i]}%" for i in range(n))}')
    print(f'   Победы: {", ".join(f"К{i+1}={wins[i]}" for i in range(n))}, паритет: {ties}')


if __name__ == '__main__':
    main()
