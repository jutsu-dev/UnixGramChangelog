from unixgram_changelog.formatting import is_valid_source_url, render_entry
from unixgram_changelog.models import ChangeEntry, ChangeKind


def test_dynamic_content_is_escaped() -> None:
    text = render_entry(ChangeEntry(
        title="<new> & fixed",
        summary="unsafe <script>",
        kind=ChangeKind.FIX,
        source_name="Unix & Gram",
        source_url="https://example.com/?a=1&b=2",
    ))
    assert "&lt;new&gt; &amp; fixed" in text
    assert "unsafe &lt;script&gt;" in text
    assert "a=1&amp;b=2" in text


def test_post_has_stable_search_tags() -> None:
    text = render_entry(ChangeEntry(
        title="Новая функция",
        summary="Описание",
        kind=ChangeKind.FEATURE,
        source_name="UnixGram",
    ))
    assert "#feature" in text
    assert "#UnixGramChangelog" in text


def test_unsafe_source_scheme_is_not_linked() -> None:
    text = render_entry(ChangeEntry(
        title="Change",
        summary="Description",
        kind=ChangeKind.TECHNICAL,
        source_name="Source",
        source_url="javascript:alert(1)",
    ))
    assert "javascript:" not in text
    assert "источник: Source" in text
    assert not is_valid_source_url("javascript:alert(1)")
    assert is_valid_source_url("https://unixgram.com/changelog/1")


def test_long_dynamic_content_stays_within_telegram_limit() -> None:
    text = render_entry(ChangeEntry(
        title="T" * 500,
        summary="S" * 5000,
        kind=ChangeKind.CLIENT,
        source_name="UnixGram",
        evidence="E" * 1000,
    ))
    assert len(text) < 4096
