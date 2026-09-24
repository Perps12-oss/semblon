"""Shared Cluster Review chrome — one document, two hosts (export + Home / review-ui)."""

from __future__ import annotations

from semblon.review_chrome.board_dto import build_chrome_board
from semblon.review_chrome.host import host_review_chrome, write_snapshot_html
from semblon.review_chrome.render import (
    PACKAGE_DIR,
    render_review_document,
    render_review_document_from_store,
)

__all__ = [
    "PACKAGE_DIR",
    "build_chrome_board",
    "host_review_chrome",
    "render_review_document",
    "render_review_document_from_store",
    "write_snapshot_html",
]
