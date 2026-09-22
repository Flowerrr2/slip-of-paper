# Third-party components

This desktop application uses:

- Python 3.11, distributed under the Python Software Foundation License.
  https://docs.python.org/3/license.html
- Qt for Python / PySide6 6.11.2, Shiboken6 and Qt 6, provided by The Qt Company
  and contributors under their applicable LGPL/GPL/commercial licensing terms.
  This build uses the open-source distributions, with Qt provided as replaceable
  dynamically linked DLLs in `_internal`. License texts shipped with those
  distributions are included in `licenses` and/or `_internal`.
  https://www.qt.io/licensing/open-source-lgpl-obligations
  https://code.qt.io/cgit/pyside/pyside-setup.git/
  https://code.qt.io/cgit/qt/
- PyInstaller 6.22.3 is used for packaging under GPL with its bootloader exception.
  https://pyinstaller.org/en/stable/license.html

Qt/PySide source for the corresponding versions is available from the upstream
repositories above. Application source is included in the delivered workspace.
The packaging is directory based; do not remove or rename the Qt DLLs or plugin
directories. No third-party image, icon or font assets are downloaded by the app.
