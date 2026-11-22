# Third-party components

The MIT license covers this project's original source only. Dependencies retain
their own copyrights and licenses. Qt/PySide/Shiboken are used under the LGPLv3
option; the GPLv3 text is included because LGPLv3 incorporates it. No Qt source
modifications are made. Bundled Qt libraries are dynamically linked in the app's
internal directory and can be replaced with ABI-compatible versions. You can also
rebuild this fully available application source against your own Qt installation.

Upstream source and build instructions:

- Qt source archives: https://download.qt.io/official_releases/qt/
- Qt for Python source archives: https://download.qt.io/official_releases/QtForPython/
- PySide/Shiboken source: https://code.qt.io/cgit/pyside/pyside-setup.git/
- Qt licensing: https://doc.qt.io/qtforpython-6/licenses.html

The build helper copies dependency license/copyright files and a version manifest
into `dist/third-party-licenses`. Refer to that manifest for the versions in a
specific build. Those notices can include build tools present in the environment,
not all of which are part of the executable. Python and other runtime components
retain the license files supplied by their upstream distributions and PyInstaller.
