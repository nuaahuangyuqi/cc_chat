"""Create only public assets: icon and standalone Python client wheel."""

import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from ccask import __version__
from ccask.sdk_info import SDK_WHEEL

MAC = Path(__file__).resolve().parents[1]
ROOT = MAC.parents[1]
icon = Image.new("RGBA", (1024, 1024))
draw = ImageDraw.Draw(icon)
draw.rounded_rectangle((42, 42, 982, 982), radius=220, fill="#171717")
draw.line([(270, 720), (512, 300), (754, 720)], fill="white", width=65, joint="curve")
draw.line([(376, 562), (648, 562)], fill="white", width=58)
icon.save(MAC / "packaging/CCAsk.icns", format="ICNS")
icon.resize((256, 256)).save(ROOT / "src/ccask/static/icon.png")

sdk = ROOT / "src/ccask/sdk"
sdk.mkdir(exist_ok=True)
name = f"ccask_client-{__version__}"
info = f"{name}.dist-info"
files = {
    f"ccask/{p}": (ROOT / "src/ccask" / p).read_bytes()
    for p in ["__init__.py", "client.py", "errors.py"]
}
files[f"{info}/METADATA"] = f"""Metadata-Version: 2.1
Name: ccask-client
Version: {__version__}
Summary: Python client for the local CC Ask desktop app
Requires-Python: >=3.7
Requires-Dist: httpx>=0.24.1,<0.25; python_version < "3.8"
Requires-Dist: httpx>=0.28,<1; python_version >= "3.8"
""".encode()
files[f"{info}/WHEEL"] = (
    b"Wheel-Version: 1.0\nGenerator: ccask\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
)
records = io.StringIO()
writer = csv.writer(records, lineterminator="\n")
for path, data in files.items():
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    writer.writerow([path, "sha256=" + digest, len(data)])
writer.writerow([f"{info}/RECORD", "", ""])
files[f"{info}/RECORD"] = records.getvalue().encode()
with zipfile.ZipFile(sdk / SDK_WHEEL, "w", zipfile.ZIP_DEFLATED) as wheel:
    for path, data in files.items():
        wheel.writestr(path, data)
# Keep older wheels available for existing installations and historical downloads.
