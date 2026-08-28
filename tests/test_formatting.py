from unixgram_changelog.formatting import (
    is_valid_source_url,
    plain_review_card,
    render_entry,
    render_review_card,
)
from unixgram_changelog.models import ChangeEntry, ChangeKind


def test_dynamic_content_is_escaped() -> None:
    text = render_entry(
        ChangeEntry(
            title="<new> & fixed",
            summary="unsafe <script>",
            kind=ChangeKind.FIX,
            source_name="Unix & Gram",
            source_url="https://example.com/?a=1&b=2",
            archive_label="GitHub",
            archive_url="https://github.com/jutsu-dev/UnixGramChangelog",
        )
    )
    assert "&lt;new&gt; &amp; fixed" in text
    assert "unsafe &lt;script&gt;" in text
    assert "a=1&amp;b=2" in text


def test_post_has_stable_search_tags() -> None:
    text = render_entry(
        ChangeEntry(
            title="Новая функция",
            summary="Описание",
            kind=ChangeKind.FEATURE,
            source_name="UnixGram",
        )
    )
    assert "#feature" in text
    assert "#UnixGramChangelog" in text


def test_snapshot_post_can_omit_service_summary() -> None:
    text = render_entry(
        ChangeEntry(
            title="Новые изменения UnixGram",
            summary="",
            kind=ChangeKind.TECHNICAL,
            source_name="UnixGram",
            source_url="https://unixgram.com/",
            changed_files=("unixgram/chunks/app/layout.json",),
        )
    )
    assert "Нужно проверить интерфейс" not in text
    assert "📄 <code>unixgram/chunks/app/layout.json</code>" in text


def test_snapshot_post_uses_compact_github_layout() -> None:
    text = render_entry(
        ChangeEntry(
            title="Новые изменения UnixGram",
            summary="",
            kind=ChangeKind.TECHNICAL,
            source_name="UnixGram",
            source_url="https://unixgram.com/",
            archive_label="jutsu-dev/UnixGramChangelog@abc1234",
            archive_url="https://github.com/jutsu-dev/UnixGramChangelog/commit/abc1234",
            changed_files=("unixgram/chunks/app/layout.json", "unixgram/css/app.json"),
            tags=("web",),
        )
    )
    assert text.startswith("<b>Новые изменения UnixGram</b>")
    assert "<b>UnixGram Changelog</b>" not in text
    assert "Источник ·" not in text
    assert "GitHub · " in text
    assert "#web" in text


def test_unsafe_source_scheme_is_not_linked() -> None:
    text = render_entry(
        ChangeEntry(
            title="Change",
            summary="Description",
            kind=ChangeKind.TECHNICAL,
            source_name="Source",
            source_url="javascript:alert(1)",
        )
    )
    assert "javascript:" not in text
    assert "Source" in text
    assert not is_valid_source_url("javascript:alert(1)")
    assert is_valid_source_url("https://unixgram.com/changelog/1")


def test_review_card_uses_compact_layout_and_hidden_evidence() -> None:
    text = render_review_card(
        ChangeEntry(
            title="UnixGram: новая сборка",
            summary="Обновился набор клиентских ресурсов.",
            kind=ChangeKind.TECHNICAL,
            source_name="UnixGram",
            source_url="https://unixgram.com/",
            archive_label="jutsu-dev/UnixGramChangelog@abc1234",
            archive_url="https://github.com/jutsu-dev/UnixGramChangelog/blob/main/archive/test.md",
            changed_files=("layout.js", "webpack.js", "app.css", "extra.js", "vendor.js"),
            evidence="build old -> new",
        )
    )
    assert "<b>UnixGram: новая сборка</b>" in text
    assert "📄 <code>layout.js</code>" in text
    assert "и ещё 1 файла" in text
    assert "<blockquote expandable><b>Технические данные</b>" in text


def test_review_card_omits_blank_summary() -> None:
    text = render_review_card(
        ChangeEntry(
            title="Новые изменения UnixGram",
            summary="",
            kind=ChangeKind.TECHNICAL,
            source_name="UnixGram",
            source_url="https://unixgram.com/",
            archive_label="jutsu-dev/UnixGramChangelog@abc1234",
            archive_url="https://github.com/jutsu-dev/UnixGramChangelog/commit/abc1234",
            changed_files=("unixgram/layout.json",),
        )
    )
    assert "Новые изменения UnixGram" in text
    assert "📄 <code>unixgram/layout.json</code>" in text
    assert "\n\n\n" not in text


def test_plain_review_card_contains_archive_reference() -> None:
    text = plain_review_card(
        ChangeEntry(
            title="UnixPlace lots API: изменился API-контракт",
            summary="Структура ответа изменилась.",
            kind=ChangeKind.API,
            source_name="UnixPlace lots API",
            source_url="https://place.unixgram.com/api/lots",
            archive_url="https://github.com/jutsu-dev/UnixGramChangelog",
        )
    )
    assert "github: https://github.com/jutsu-dev/UnixGramChangelog" in text


def test_long_dynamic_content_stays_within_telegram_limit() -> None:
    text = render_entry(
        ChangeEntry(
            title="T" * 500,
            summary="S" * 5000,
            kind=ChangeKind.CLIENT,
            source_name="UnixGram",
            evidence="E" * 1000,
        )
    )
    assert len(text) <= 4096
