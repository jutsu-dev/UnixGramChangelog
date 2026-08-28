# Changelog

Все заметные изменения проекта фиксируются здесь. Формат основан на Keep a Changelog, версии следуют Semantic Versioning.

## [Unreleased]

### Added

- закрытая owner-only граница доступа до Telegram handlers;
- компактная редакционная панель и меню быстрых действий;
- premium emoji из Telegram iOS Icons с обычным fallback;
- отдельный список команд только для чата владельца;
- новый GitHub hero, документация и private repository policy;
- CODEOWNERS, pinned GitHub Actions и усиленная systemd-изоляция;
- review-first Telegram workflow;
- девять категорий изменений;
- SQLite-история и защита от дублей;
- HTML-предпросмотр с plain-text fallback;
- расширяемый протокол источников;
- документация, CI и контейнерный запуск.

### Changed

- конфигурация требует ровно один Telegram ID владельца;
- лицензия заменена на All rights reserved;
- production env проверяется на владельца и права перед deploy.
