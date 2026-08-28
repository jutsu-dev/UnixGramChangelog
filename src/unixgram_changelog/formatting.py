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


def _render_source(source_name: str, source_url: str | None) -> str:
    safe_name = escape(source_name)
    if source_url and urlsplit(source_url).scheme in {"http", "https"}:
        safe_url = escape(source_url, quote=True)
        return f'<a href="{safe_url}">{safe_name}</a>'
    return safe_name


def is_valid_source_url(source_url: str | None) -> bool:
    if not source_url:
        return False
    parsed = urlsplit(source_url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _maybe_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def render_entry(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    all_tags = normalize_tags((*entry.tags, tag, "unixgramchangelog"))
    details: list[str] = [f"{code} {label}"]
    if entry.version:
        details.append(f"v{escape(entry.version)}")
    if entry.occurred_at:
        details.append(entry.occurred_at.strftime("%d.%m.%Y"))

    lines = [
        "<b>UnixGram Changelog</b>",
        f"<b>{escape(_maybe_trim(entry.title, 140))}</b>",
        f"<blockquote>{' · '.join(details)}</blockquote>",
        "",
        escape(_maybe_trim(entry.summary, 2400)),
        "",
        f"🔗 {_render_source(entry.source_name, entry.source_url)}",
    ]

    if all_tags:
        rendered_tags = [
            "#UnixGramChangelog" if item == "unixgramchangelog" else f"#{item}"
            for item in all_tags
        ]
        lines.extend(("", " ".join(rendered_tags)))

    return "\n".join(lines)


def plain_entry(entry: ChangeEntry) -> str:
    code, label, tag = KIND_META[entry.kind]
    tags = normalize_tags((*entry.tags, tag, "unixgramchangelog"))
    parts = [
        f"{code} | {label}",
        entry.title,
        "",
        entry.summary,
        "",
        f"source: {entry.source_name}",
    ]
    if entry.source_url:
        parts.append(entry.source_url)
    if entry.evidence:
        parts.append(f"evidence: {entry.evidence}")
    if tags:
        rendered_tags = [
            "#UnixGramChangelog" if item == "unixgramchangelog" else f"#{item}"
            for item in tags
        ]
        parts.extend(("", " ".join(rendered_tags)))
    return _maybe_trim("\n".join(parts), MAX_MESSAGE_LENGTH)


def render_review_card(entry: ChangeEntry) -> str:
    _, label, tag = KIND_META[entry.kind]
    review = [
        "<b>Найдено новое изменение</b>",
        f"{escape(entry.source_name)} · {escape(label)} · #{tag}",
        "",
        render_entry(entry),
    ]
    if entry.evidence:
        review.extend(
            (
                "",
                "<blockquote expandable><b>Технические данные</b>\n"
                f"{escape(_maybe_trim(entry.evidence, 700))}</blockquote>",
            )
        )
    return "\n".join(review)


def plain_review_card(entry: ChangeEntry) -> str:
    _, label, tag = KIND_META[entry.kind]
    rows = [
        "Найдено новое изменение",
        f"{entry.source_name} · {label} · #{tag}",
    ]
    rows.extend(("", plain_entry(entry)))
    if entry.evidence:
        rows.extend(("", "Технические данные", _maybe_trim(entry.evidence, 700)))
    return "\n".join(rows)


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
