from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1] / "data" / "snapshots"
SITES = {
    "unixgram": "https://unixgram.com/",
    "unixplace": "https://place.unixgram.com/",
}
ASSET_PATTERN = re.compile(
    r'(?:src|href)=["\']([^"\']+_next/static/[^"\']+\.(?:js|css)(?:\?[^"\']*)?)["\']'
)
HASHED_NAME = re.compile(r"-([0-9a-f]{8,})(?=\.(?:js|css)$)")


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "UnixGramChangelog/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type != "text/html":
            raise RuntimeError(f"unexpected content type for {url}: {content_type}")
        body: bytes = response.read()
        return body.decode("utf-8")


def safe_record_path(asset_url: str) -> tuple[Path, str | None]:
    asset_path = urlsplit(asset_url).path.split("/_next/static/", 1)[1]
    parts = list(PurePosixPath(asset_path).parts)
    filename = parts[-1]
    match = HASHED_NAME.search(filename)
    asset_hash = match.group(1) if match else None
    stable_name = HASHED_NAME.sub("", filename).rsplit(".", 1)[0]
    parts[-1] = stable_name + ".json"
    return Path(*parts), asset_hash


def snapshot_site(slug: str, base_url: str) -> None:
    html = fetch_text(base_url)
    if len(html) < 1000 or "_next/static" not in html:
        raise RuntimeError(f"unexpected document from {base_url}")
    assets = sorted({urljoin(base_url, item) for item in ASSET_PATTERN.findall(html)})
    if not assets:
        raise RuntimeError(f"no Next.js assets found at {base_url}")

    site_root = ROOT / slug
    expected: set[Path] = set()
    manifest: list[dict[str, object]] = []
    for asset_url in assets:
        relative_path, asset_hash = safe_record_path(asset_url)
        record_path = site_root / relative_path
        expected.add(record_path)
        record = {
            "asset": urlsplit(asset_url).path,
            "hash": asset_hash,
            "kind": record_path.parent.name,
        }
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest.append(record)

    manifest_path = site_root / "_manifest.json"
    expected.add(manifest_path)
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(
            {"site": base_url, "fingerprint": fingerprint, "assets": len(assets)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for stale in site_root.rglob("*.json"):
        if stale not in expected:
            stale.unlink()


def main() -> None:
    for slug, base_url in SITES.items():
        snapshot_site(slug, base_url)


if __name__ == "__main__":
    main()
