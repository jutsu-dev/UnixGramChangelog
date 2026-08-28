from __future__ import annotations

import re
from html import escape
from urllib.parse import urlsplit

from .models import ChangeEntry, ChangeKind, EntryStatus, SourceMode, SourceRecord

KIND_META: dict[ChangeKind, tuple[str, str, str]] = {
    ChangeKind.FEATURE: ("✨", "Новая функция", "feature"),
    ChangeKind.INTERFACE: ("🎨", "Интерфейс", "interface"),
    ChangeKind.FIX: ("🛠", "Исправление", "fix"),
    ChangeKind.TECHNICAL: ("⚙️", "Техническое", "technical"),
    ChangeKind.EXPERIMENT: ("🧪", "Эксперимент", "experiment"),
    ChangeKind.DISCOVERY: ("🔎", "Обнаружено", "discovery"),
    ChangeKind.API: ("🔌", "API", "api"),
    ChangeKind.CLIENT: ("📱", "Клиент", "client"),
    ChangeKind.IMPORTANT: ("🚨", "Важное обновление", "important"),
}

MAX_MESSAGE_LENGTH = 4096


def normalize_tag(tag: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "", tag.strip().casefold().replace("-", "_"))
    return cleaned


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    unique: list[str] = []
    for raw_tag in tags:
        tag = normalize_tag(raw_tag.lstrip("#"))
        if tag and tag not in unique:
            unique.append(tag)
    return tuple(unique)


def is_valid_source_url(source_url: str | None) -> bool:
    if not source_url:
        return False
    parsed = urlsplit(source_url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _render_link(label: str, url: str | None) -> str | None:
    if not is_valid_source_url(url):
        return None
    assert url is not None
    safe_url = escape(url, quote=True)
    return f'<a href="{safe_url}">{escape(label)}</a>'


def _render_source(source_name: str, source_url: str | None) -> str:
    return _render_link(source_name, source_url) or escape(source_name)


def _maybe_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _render_tags(entry: ChangeEntry, tag: str) -> str | None:
    all_tags = normalize_tags((*entry.tags, tag, "unixgramchangelog"))
    if not all_tags:
        return None
    rendered_tags = [
        "#UnixGramChangelog" if item == "unixgramchangelog" else f"#{item}"
        for item in all_tags
    ]
    return " ".join(rendered_tags)


def _render_changed_files(entry: ChangeEntry) -> list[str]:
    rows: list[str] = []
    if not entry.changed_files:
        return rows
    for item in entry.changed_files[:4]:
        rows.append(f"📄 <code>{escape(_maybe_trim(item, 72))}</code>")
    if len(entry.changed_files) > 4:
        rows.append(f"и ещё {len(entry.changed_files) - 4} файла")
    return rows


def _render_archive_row(entry: ChangeEntry) -> str | None:
    archive = _render_link(entry.archive_label or "GitHub", entry.archive_url)
    if archive:
        return f"GitHub · {archive}"
    if entry.archive_label is not None:
        return f"GitHub · {escape(entry.archive_label)}"
    return None


def _render_source_row(entry: ChangeEntry) -> str:
    return f"Источник · {_render_source(entry.source_name, entry.source_url)}"


def render_entry(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    details: list[str] = [f"{code} {label}"]
    if entry.version:
        details.append(f"v{escape(entry.version)}")
    if entry.occurred_at:
        details.append(entry.occurred_at.strftime("%d.%m.%Y"))

    lines = [
        "<b>UnixGram Changelog</b>",
        f"<b>{escape(_maybe_trim(entry.title, 140))}</b>",
    ]
    if details:
        lines.extend(("", " · ".join(details)))

    changed_files = _render_changed_files(entry)
    if changed_files:
        lines.extend(("", *changed_files))
    else:
        lines.extend(("", escape(_maybe_trim(entry.summary, 900))))

    archive_row = _render_archive_row(entry)
    if archive_row:
        lines.extend(("", archive_row))
    lines.append(_render_source_row(entry))

    tags = _render_tags(entry, tag)
    if tags:
        lines.extend(("", tags))

    return _maybe_trim("\n".join(lines), MAX_MESSAGE_LENGTH)


def plain_entry(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    parts = [
        f"{code} | {label}",
        entry.title,
    ]
    if entry.changed_files:
        parts.extend(("", *entry.changed_files[:4]))
        if len(entry.changed_files) > 4:
            parts.append(f"+{len(entry.changed_files) - 4} more files")
    else:
        parts.extend(("", entry.summary))
    if entry.archive_label:
        parts.extend(("", f"github: {entry.archive_label}"))
    elif entry.archive_url:
        parts.extend(("", "github"))
    parts.extend(("", f"source: {entry.source_name}"))
    if entry.archive_url:
        parts.append(entry.archive_url)
    if entry.source_url:
        parts.append(entry.source_url)
    if entry.evidence:
        parts.extend(("", "evidence:", entry.evidence))
    tags = _render_tags(entry, tag)
    if tags:
        parts.extend(("", tags))
    return _maybe_trim("\n".join(parts), MAX_MESSAGE_LENGTH)


def render_review_card(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    lines = [
        f"<b>{escape(_maybe_trim(entry.title, 140))}</b>",
        f"<blockquote>{code} {escape(label)} · {escape(entry.source_name)} · #{tag}</blockquote>",
    ]

    changed_files = _render_changed_files(entry)
    if changed_files:
        lines.extend(("", *changed_files))
    else:
        lines.extend(("", escape(_maybe_trim(entry.summary, 720))))

    archive_row = _render_archive_row(entry)
    if archive_row:
        lines.extend(("", archive_row))
    lines.append(_render_source_row(entry))

    if entry.evidence:
        lines.extend(
            (
                "",
                "<blockquote expandable><b>Технические данные</b>\n"
                f"{escape(_maybe_trim(entry.evidence, 900))}</blockquote>",
            )
        )
    return _maybe_trim("\n".join(lines), MAX_MESSAGE_LENGTH)


def plain_review_card(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    rows = [
        entry.title,
        f"{code} {label} · {entry.source_name} · #{tag}",
    ]
    if entry.changed_files:
        rows.extend(("", *entry.changed_files[:4]))
        if len(entry.changed_files) > 4:
            rows.append(f"+{len(entry.changed_files) - 4} more files")
    else:
        rows.extend(("", entry.summary))
    if entry.archive_url:
        rows.extend(("", f"github: {entry.archive_url}"))
    if entry.source_url:
        rows.extend(("", f"source: {entry.source_url}"))
    if entry.evidence:
        rows.extend(("", "Технические данные", _maybe_trim(entry.evidence, 900)))
    return _maybe_trim("\n".join(rows), MAX_MESSAGE_LENGTH)


def render_source_card(source: SourceRecord) -> str:
    title = escape(source.name)
    rows = [
        f"<b>{title}</b>",
        f"slug: <code>{escape(source.slug)}</code>",
        f"mode: <code>{source.mode.value}</code>",
        f"enabled: <code>{'yes' if source.enabled else 'no'}</code>",
        f"threshold: <code>{source.confidence_threshold:.2f}</code>",
    ]
    if source.default_kind:
        rows.append(f"default kind: <code>{escape(source.default_kind.value)}</code>")
    if source.url:
        safe_url = escape(source.url, quote=True)
        rows.append(f'source url: <a href="{safe_url}">{escape(source.url)}</a>')
    if source.notes:
        rows.append(f"notes: {escape(_maybe_trim(source.notes, 240))}")
    return "\n".join(rows)


def plain_source_card(source: SourceRecord) -> str:
    rows = [
        source.name,
        f"slug: {source.slug}",
        f"mode: {source.mode.value}",
        f"enabled: {'yes' if source.enabled else 'no'}",
        f"threshold: {source.confidence_threshold:.2f}",
    ]
    if source.default_kind:
        rows.append(f"default kind: {source.default_kind.value}")
    if source.url:
        rows.append(f"source url: {source.url}")
    if source.notes:
        rows.append(f"notes: {source.notes}")
    return "\n".join(rows)


def render_history_line(entry: ChangeEntry) -> str:
    _, label, tag = KIND_META[entry.kind]
    entry_id = entry.id if entry.id is not None else "-"
    return (
        f"<code>#{entry_id}</code> "
        f"<b>{escape(_maybe_trim(entry.title, 72))}</b> "
        f"<blockquote>{label} · #{tag}</blockquote>"
    )


def default_source_mode_label(mode: SourceMode) -> str:
    return "auto publish" if mode is SourceMode.AUTO else "review first"


def entry_status_label(status: EntryStatus) -> str:
    return status.value.replace("_", " ")
