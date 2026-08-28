<div align="center">
  <img src="docs/assets/unixgram-changelog-hero.png" width="100%" alt="UnixGram Changelog">

# UnixGram Changelog

Бот для публикации изменений UnixGram.

Он автоматически проверяет сборки UnixGram и UnixPlace, следит за публичным API-контрактом UnixPlace и складывает найденные изменения в закрытую очередь владельца. Первая проверка создаёт базовую точку без уведомления. Публикация в канал всегда требует подтверждения.

[![CI](https://github.com/jutsu-dev/UnixGramChangelog/actions/workflows/ci.yml/badge.svg)](https://github.com/jutsu-dev/UnixGramChangelog/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-151515?logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3-151515?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![License](https://img.shields.io/badge/license-all_rights_reserved-151515)](LICENSE)

[Канал](https://t.me/UnixGramChangelog) · [Бот](https://t.me/UnixGramChangelogBot) · [UnixGram History](https://t.me/unixgramhistory)
</div>

## Как это работает

Изменение сначала попадает в очередь. Владелец проверяет текст и источник, затем публикует или отклоняет запись. Повторные записи бот отсекает по fingerprint.

```text
/new feature | Заголовок | Что изменилось | UnixGram | https://unixgram.com/...
```

Ссылка на источник обязательна. После публикации бот сохраняет Telegram message ID и статус записи в SQLite.

## Меню бота

| Кнопка | Действие |
|---|---|
| `Новая запись` | показывает формат команды `/new` |
| `Очередь` | открывает записи на проверке |
| `История` | показывает последние публикации |
| `Категории` | выводит допустимые типы изменений |
| `Канал` | открывает `@UnixGramChangelog` |

Для карточки в очереди доступны кнопки `Опубликовать` и `Отклонить`.

В меню используются эмодзи из набора [Telegram iOS Icons](https://t.me/addemoji/tgiosicons). Если custom emoji недоступны, бот отправляет обычные Unicode-иконки.

## Формат публикации

Каждый пост содержит:

- категорию изменения;
- заголовок и короткое описание;
- ссылку на источник;
- теги для поиска по каналу.

Динамический текст экранируется перед отправкой. Если Telegram отклоняет HTML-разметку, публикация повторяется обычным текстом.

Категории и ограничения описаны в [CHANGELOG_FORMAT.md](docs/CHANGELOG_FORMAT.md).

## Доступ

Production-бот принимает команды только от Telegram ID владельца и только в личном чате. Остальные сообщения и нажатия игнорируются.

Токен, SSH-ключи, база и production-конфигурация в репозиторий не добавляются. Они хранятся на VPS и в GitHub Secrets.

Исходный код доступен для просмотра. Разрешение на самостоятельный запуск, копирование, изменение или хостинг не предоставляется. Условия находятся в [LICENSE](LICENSE).

## Структура

```text
src/unixgram_changelog/
├── access.py        проверка владельца
├── bot.py           команды и обработчики
├── formatting.py    оформление публикаций
├── ingestion.py     приём новых записей
├── notifications.py уведомления владельца
├── publisher.py     отправка в канал
├── storage.py       SQLite и защита от дублей
├── ui.py            кнопки и эмодзи
└── sources/         адаптеры источников
```

Документация:

- [архитектура](docs/ARCHITECTURE.md)
- [формат changelog](docs/CHANGELOG_FORMAT.md)
- [добавление источника](docs/ADDING_A_SOURCE.md)
- [deploy и rollback](docs/DEPLOY.md)
- [безопасность](docs/SECURITY.md)

## Проверки

```bash
ruff check .
mypy src
pytest -q
```

Те же проверки выполняются в GitHub Actions перед deploy.

## Статус

Проект поддерживает [UnixGram History](https://t.me/unixgramhistory). Это независимый проект сообщества, не официальный продукт команды UnixGram.

© 2026 UnixGram History. [All rights reserved](LICENSE).
