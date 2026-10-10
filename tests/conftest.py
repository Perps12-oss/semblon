import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Semblon")
    app.setOrganizationName("Semblon")
    yield app
    app.processEvents()
    app.quit()
