# Run from the project root with release/mac/scripts/build_macos.sh.
from pathlib import Path
import platform
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
from ccask import __version__

mac = Path(SPECPATH).parent
root = mac.parents[1]
# Explicit allowlist: never collect a home directory, auth cache, DB or user configuration.
datas = [(str(root / 'src/ccask/static'), 'ccask/static'),
         (str(root / 'src/ccask/sdk'), 'ccask/sdk')]
datas += collect_data_files('webview') + copy_metadata('pywebview')
a = Analysis([str(mac / 'packaging/desktop_entry.py')],
             pathex=[str(root / 'src'), str(mac / 'src')], datas=datas,
             hiddenimports=['webview.platforms.cocoa', 'uvicorn.logging',
                            'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
                            'uvicorn.lifespan.on'],
             excludes=['pytest', 'PIL', 'tkinter', 'webview.platforms.qt',
                       'webview.platforms.gtk', 'webview.platforms.winforms'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CC Ask',
          debug=False, strip=False, upx=False, console=False,
          argv_emulation=False, target_arch=platform.machine(), codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CC Ask')
app = BUNDLE(coll, name='CC Ask.app', icon=str(mac / 'packaging/CCAsk.icns'),
             bundle_identifier='local.ccask.desktop', version=__version__,
             info_plist={'CFBundleDisplayName': 'CC Ask', 'CFBundleShortVersionString': __version__,
                         'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '14.0',
                         'NSHumanReadableCopyright': 'CC Ask · Personal use',
                         'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True}})
