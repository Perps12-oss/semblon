"""Grid thumbs are written once beside the store and read back after that."""

from PySide6.QtGui import QColor, QImage

from semblon.native_shell.images import (
    clear_decoded_frames,
    clear_thumb_cache,
    image_decode_count,
    load_display_image,
    reset_image_cache,
    thumb_cache_dir,
)


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
