"""Grid thumbs are written once beside the store and read back after that."""

from PySide6.QtGui import QColor, QImage

from semblon.native_shell.images import (
    clear_decoded_frames,
    clear_thumb_cache,
    image_decode_count,
    load_display_image,
    peek_display_image,
    read_cached_thumb,
    read_cached_thumb_any_tier,
    reset_image_cache,
    thumb_cache_dir,
    thumb_on_disk,
)
from semblon.native_shell import images as image_mod


def _png(path) -> None:
    image = QImage(48, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path), "PNG")


def test_second_thumb_reads_the_jpeg_instead_of_the_original(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    first = load_display_image(str(source), 384, cache_dir=cache)
    assert not first.isNull()
    assert image_decode_count() == 1
    written = list(cache.rglob("*.jpg"))
    assert len(written) == 1
    clear_decoded_frames()
    second = load_display_image(str(source), 160, cache_dir=cache)
    assert not second.isNull()
    assert image_decode_count() == 1
    assert second.width() == first.width()
    assert second.height() == first.height()


def test_a_changed_file_decodes_again(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = thumb_cache_dir(tmp_path / "library.sqlite")
    load_display_image(str(source), 384, cache_dir=cache)
    assert image_decode_count() == 1
    image = QImage(48, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    assert image.save(str(source), "PNG")
    # Same mtime can collapse on a fast filesystem; force a new key.
    stat = source.stat()
    os_utime = __import__("os").utime
    os_utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    clear_decoded_frames()
    again = load_display_image(str(source), 384, cache_dir=cache)
    assert not again.isNull()
    assert image_decode_count() == 2


def test_clear_thumb_cache_removes_the_directory(tmp_path):
    store = tmp_path / "library.sqlite"
    store.write_bytes(b"")
    cache = thumb_cache_dir(store)
    source = tmp_path / "photo.png"
    _png(source)
    load_display_image(str(source), 384, cache_dir=cache)
    assert cache.is_dir()
    clear_thumb_cache(store)
    assert not cache.exists()


def test_thumb_on_disk_does_not_generate(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    assert thumb_on_disk(str(source), 96, cache_dir=cache) is False
    assert thumb_on_disk(str(source), 384, cache_dir=cache) is False
    assert image_decode_count() == 0
    assert list(cache.rglob("*.jpg")) == []
    load_display_image(str(source), 96, cache_dir=cache)
    assert thumb_on_disk(str(source), 96, cache_dir=cache) is True
    assert image_decode_count() == 1


def test_read_cached_thumb_never_decodes_original(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    assert read_cached_thumb(str(source), 96, cache_dir=cache) is image_mod._MISS
    assert image_decode_count() == 0
    load_display_image(str(source), 96, cache_dir=cache)
    assert image_decode_count() == 1
    clear_decoded_frames()
    assert peek_display_image(str(source), 96, cache_dir=cache) is image_mod._MISS
    again = read_cached_thumb(str(source), 96, cache_dir=cache)
    assert again is not image_mod._MISS
    assert not again.isNull()
    assert image_decode_count() == 1


def test_require_disk_drops_stale_memory_after_thumb_deleted(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    load_display_image(str(source), 96, cache_dir=cache)
    assert image_decode_count() == 1
    # Memory still warm; delete the disk JPEG (replaced/cleared thumb).
    for jpg in cache.rglob("*.jpg"):
        jpg.unlink()
    assert thumb_on_disk(str(source), 96, cache_dir=cache) is False
    assert read_cached_thumb(str(source), 96, cache_dir=cache, require_disk=False) is not image_mod._MISS
    assert read_cached_thumb(str(source), 96, cache_dir=cache, require_disk=True) is image_mod._MISS
    assert image_decode_count() == 1


def test_cache_only_archive_response_does_not_decode(tmp_path):
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    from semblon.native_shell.images import ArchiveImageResponse

    response = ArchiveImageResponse(str(source), 96, cache, cache_only=True)
    response.start()
    # Miss path finishes empty without scheduling a decode.
    assert image_decode_count() == 0
    load_display_image(str(source), 96, cache_dir=cache)
    assert image_decode_count() == 1
    clear_decoded_frames()
    warm = ArchiveImageResponse(str(source), 96, cache, cache_only=True)
    warm.start()
    assert image_decode_count() == 1


def test_cs_falls_back_to_384_when_only_large_tier_on_disk(tmp_path):
    """Ribbon may mark hasTiny from 384 while QML cs/ prefers 96 — still paint."""
    reset_image_cache()
    source = tmp_path / "photo.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    # Warm only the 384 disk tier (Roll / Focus path).
    load_display_image(str(source), 384, cache_dir=cache)
    assert image_decode_count() == 1
    assert thumb_on_disk(str(source), 384, cache_dir=cache) is True
    assert thumb_on_disk(str(source), 96, cache_dir=cache) is False
    clear_decoded_frames()

    # Strict 96 peek misses; any-tier and cs/ must hit 384 without decoding.
    assert read_cached_thumb(str(source), 96, cache_dir=cache, require_disk=True) is image_mod._MISS
    any_tier = read_cached_thumb_any_tier(str(source), cache_dir=cache, prefer_tiny=True)
    assert any_tier is not image_mod._MISS
    assert not any_tier.isNull()
    assert image_decode_count() == 1

    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.images import ArchiveImageProvider

    app = QApplication.instance() or QApplication([])
    provider = ArchiveImageProvider(lambda _mid: str(source), cache)
    response = provider.requestImageResponse("cs/media-large-only", None)
    end = __import__("time").monotonic() + 0.4
    while __import__("time").monotonic() < end:
        app.processEvents()
        __import__("time").sleep(0.01)
    assert image_decode_count() == 1
    assert not response._image.isNull()
