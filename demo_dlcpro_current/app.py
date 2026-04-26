from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo_dlcpro_current.window import DemoMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = DemoMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
