#!/usr/bin/env python3
"""
build_audit.py — собирает HTML-артефакт UX-аудита из шаблона и JSON-данных.

Использование:
  python3 build_audit.py \\
    --data /tmp/audit-data.json \\
    --template references/html-template.html \\
    --output /mnt/user-data/outputs/ux-audit-NAME.html

Структура JSON (audit-data.json):
{
  "title": "UX-аудит",
  "meta": "Авито · кабинет продавца · десктоп · 1 экран",
  "screens": [
    {
      "path": "/mnt/user-data/uploads/screen1.jpg",
      "caption": "Экран 1: модалка «Все результаты»",
      "subcaption": "Аналитика объявления Fujifilm X100VI"
    }
  ],
  "figma_links": [
    {
      "url": "https://www.figma.com/file/...",
      "title": "Прототип в Figma",
      "subtitle": "Откройте, чтобы посмотреть"
    }
  ],
  "no_screenshots": false,
  "legend": "Иконки: 💰 деньги | ⛔ ошибки | 🤔 непонятно | 🐢 долго | ✨ всё хорошо",
  "rows": [
    {
      "type_icon": "🤔",
      "heuristic": "6. Узнавание",
      "problem": "Пользователь может...",
      "risk": "Откладывание правок",
      "criticality": "🟠 Средняя",
      "action": "В каждом пункте показывать..."
    }
  ],
  "score": 84,
  "main_risk": "Одна фраза",
  "first_priority": "Одна фраза"
}

Скрипт:
- Уменьшает скриншоты до 1100 px по ширине, JPEG 82%
- Кодирует в base64, встраивает в HTML
- Собирает блок превью (картинки / Figma-карточки / текстовые имена)
- Подставляет строки таблицы
- Добавляет дисклеймер про base64, если есть встроенные скрины
"""

import argparse
import base64
import html
import json
import sys
from io import BytesIO
from pathlib import Path


def encode_screenshot(path, max_width=1100, quality=82):
    """Открыть, уменьшить, сжать, закодировать в base64."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow не установлен. Установи: pip install Pillow --break-system-packages", file=sys.stderr)
        sys.exit(1)

    img = Image.open(path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def build_screen_card(screen, is_single):
    """HTML-карточка одного скриншота."""
    b64 = encode_screenshot(screen['path'])
    klass = 'screen-card single' if is_single else 'screen-card'
    caption = html.escape(screen.get('caption', 'Экран'))
    subcaption = html.escape(screen.get('subcaption', ''))
    subcaption_html = f'<div class="subcaption">{subcaption}</div>' if subcaption else ''
    return (
        f'<a class="{klass}" href="data:image/jpeg;base64,{b64}" target="_blank">'
        f'<img src="data:image/jpeg;base64,{b64}" alt="{caption}">'
        f'<div class="caption">{caption}</div>'
        f'{subcaption_html}'
        f'</a>'
    )


def build_textonly_card(screen):
    """HTML-карточка без картинки (режим без скринов или текстовое описание)."""
    caption = html.escape(screen.get('caption', 'Экран'))
    subcaption = html.escape(screen.get('subcaption', ''))
    subcaption_html = f'<div class="subcaption">{subcaption}</div>' if subcaption else ''
    return (
        f'<div class="screen-textonly">'
        f'<div class="caption">{caption}</div>'
        f'{subcaption_html}'
        f'</div>'
    )


def build_figma_card(link):
    """HTML-карточка ссылки на Figma."""
    url = html.escape(link['url'])
    title = html.escape(link.get('title', 'Прототип в Figma'))
    subtitle = html.escape(link.get('subtitle', 'Откройте, чтобы посмотреть'))
    return (
        f'<a class="figma-card" href="{url}" target="_blank">'
        f'<div class="figma-icon">F</div>'
        f'<div class="figma-text"><strong>{title}</strong><span>{subtitle}</span></div>'
        f'</a>'
    )


def build_screens_html(data):
    """Собрать блок превью."""
    screens = data.get('screens', [])
    figma_links = data.get('figma_links', [])
    no_screenshots = data.get('no_screenshots', False)

    if not screens and not figma_links:
        return '<div class="screen-textonly"><div class="caption">Визуальные материалы не приложены</div><div class="subcaption">Анализ выполнен по текстовому описанию</div></div>'

    cards = []

    if screens:
        if no_screenshots:
            cards.extend(build_textonly_card(s) for s in screens)
        else:
            is_single = len(screens) == 1 and not figma_links
            cards.extend(build_screen_card(s, is_single) for s in screens)

    if figma_links:
        cards.extend(build_figma_card(l) for l in figma_links)

    return '\n      '.join(cards)


def build_row(row):
    """Собрать одну строку таблицы."""
    type_icon = html.escape(row.get('type_icon', '✨'))
    heuristic = html.escape(row.get('heuristic', ''))
    problem = html.escape(row.get('problem', ''))
    risk = html.escape(row.get('risk', '—'))
    criticality = html.escape(row.get('criticality', '🟢 Нулевая'))
    action = html.escape(row.get('action', '—'))
    klass = ' class="good"' if criticality.startswith('🟢') else ''
    return (
        f'        <tr{klass}>'
        f'<td><span class="icon">{type_icon}</span></td>'
        f'<td>{heuristic}</td>'
        f'<td>{problem}</td>'
        f'<td>{risk}</td>'
        f'<td>{criticality}</td>'
        f'<td>{action}</td>'
        f'</tr>'
    )


def build_rows_html(rows):
    """Собрать все строки таблицы."""
    return '\n'.join(build_row(r) for r in rows)


def build_disclaimer_html(data):
    """Дисклеймер про base64-скрины, если они есть."""
    screens = data.get('screens', [])
    no_screenshots = data.get('no_screenshots', False)
    if screens and not no_screenshots:
        return (
            '<div class="disclaimer">'
            'Артефакт содержит встроенные скриншоты в base64. '
            'Учитывай при пересылке — скрины «уезжают» вместе с файлом.'
            '</div>'
        )
    return ''


def main():
    ap = argparse.ArgumentParser(description='Сборщик HTML-артефакта UX-аудита.')
    ap.add_argument('--data', required=True, help='Путь к JSON-файлу с данными аудита')
    ap.add_argument('--template', required=True, help='Путь к HTML-шаблону')
    ap.add_argument('--output', required=True, help='Куда сохранить готовый HTML')
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    template = Path(args.template).read_text(encoding='utf-8')

    replacements = {
        '{{TITLE}}': html.escape(data.get('title', 'UX-аудит')),
        '{{META}}': html.escape(data.get('meta', '')),
        '{{LEGEND}}': html.escape(data.get('legend', 'Иконки: 💰 деньги | ⛔ ошибки | 🤔 непонятно | 🐢 долго | ✨ всё хорошо')),
        '{{SCREENS_HTML}}': build_screens_html(data),
        '{{ROWS_HTML}}': build_rows_html(data.get('rows', [])),
        '{{SCORE}}': str(data.get('score', 0)),
        '{{MAIN_RISK}}': html.escape(data.get('main_risk', '—')),
        '{{FIRST_PRIORITY}}': html.escape(data.get('first_priority', '—')),
        '{{DISCLAIMER_HTML}}': build_disclaimer_html(data),
    }

    html_out = template
    for placeholder, value in replacements.items():
        html_out = html_out.replace(placeholder, value)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding='utf-8')

    size_kb = out_path.stat().st_size / 1024
    print(f'OK: {out_path} ({size_kb:.1f} КБ)')


if __name__ == '__main__':
    main()
