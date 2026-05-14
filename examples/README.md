# Примеры использования

В папке — два собранных HTML-артефакта, которые наглядно показывают, как выглядит вывод скилла, и JSON с данными, из которых они собраны.

## Файлы

- [`audit-example.html`](./audit-example.html) — пример **одиночного UX-аудита** одного экрана
- [`compare-example.html`](./compare-example.html) — пример **сравнения двух концептов**
- [`audit-data.example.json`](./audit-data.example.json) — JSON-структура для одиночного аудита
- [`compare-data.example.json`](./compare-data.example.json) — JSON-структура для сравнения

## Как посмотреть

Откройте HTML-файлы в браузере — там можно протестировать кнопки «Скачать PDF» и «Скачать JPEG».

> Примеры собраны в **NDA-режиме** — без встроенных скриншотов. Если у вас есть свои макеты, в JSON можно указать пути к ним в полях `screenshot_path` и поставить `no_screenshots: false` — скрипт встроит их в HTML.

## Как пересобрать примеры из JSON

```bash
# Из корня репозитория
pip install Pillow

python3 references/build_audit.py \
  --data examples/audit-data.example.json \
  --template references/html-template.html \
  --output examples/audit-example.html

python3 references/build_compare.py \
  --data examples/compare-data.example.json \
  --template references/html-template-compare.html \
  --output examples/compare-example.html
```

## Создать свой аудит на основе JSON

1. Скопируйте `audit-data.example.json` → `my-audit.json`.
2. Поменяйте поля `title`, `meta`, `rows`, `score`, `main_risk`, `first_priority` под свой кейс.
3. Если хотите со скриншотами — пропишите `screenshot_path` к своим файлам, поставьте `no_screenshots: false`.
4. Запустите `build_audit.py` с указанием своего JSON.

Это полезно, если вы используете данные аудита из другой системы (например, из таблицы или базы данных) и хотите автоматически генерировать визуальные отчёты, минуя Claude.
