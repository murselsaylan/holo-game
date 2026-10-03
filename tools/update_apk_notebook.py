"""Generate the checked Colab debug build workflow (ordinary Python cells)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(kind, source):
    result = {"cell_type": kind, "metadata": {}, "source": source.strip().splitlines(True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


cells = [cell("markdown", """
# HOLO — Android APK Oluşturucu

Güncel `holo_apk_source.zip` dosyasını ikinci adımda yükleyin. Hücreleri sırayla
çalıştırın. İlk derleme 20–40 dakika sürebilir. Google hesabınızla Colab'a giriş
yapmanız gerekir. Bu defter test APK'sı üretir; mağaza yayını yapmaz.

Eski derlemedeki `longintrepr.h` hatası için proje, Python 3.11 uyumlu Pygame
2.6.1 kaynak dağıtımını `android_recipes/pygame` üzerinden kullanır.
Eski v2/v3 parçalarını güncel ZIP ile karıştırmayın.
"""), cell("markdown", "## 1. Derleme araçları"), cell("code", '''
import os
import subprocess
import sys

os.environ["DEBIAN_FRONTEND"] = "noninteractive"
subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
subprocess.run(["sudo", "apt-get", "install", "-y", "-qq",
    "git", "zip", "unzip", "openjdk-17-jdk", "python3-pip", "python3-venv",
    "autoconf", "automake", "libtool", "pkg-config", "zlib1g-dev",
    "libncurses-dev", "libtinfo6", "cmake", "libffi-dev", "libssl-dev"], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade",
    "Cython==0.29.36", "buildozer", "virtualenv", "setuptools"], check=True)
print("Derleme araçları hazır.")
'''), cell("markdown", "## 2. Güncel kaynak ZIP dosyasını yükleyin"), cell("code", '''
from google.colab import files
from pathlib import Path
import tempfile
import zipfile
import os

uploaded = files.upload()
archives = [name for name in uploaded if name.lower().endswith(".zip")]
if len(archives) != 1:
    raise RuntimeError("Tek bir holo_apk_source.zip seçin; yüklemeyi iptal ettiyseniz hücreyi yeniden çalıştırın.")
# Fresh isolated directory avoids stale Pygame build caches and preserves prior work.
target_dir = Path(tempfile.mkdtemp(prefix="holo_project_", dir="/content")).resolve()
with zipfile.ZipFile(archives[0]) as archive:
    needed = {"main.py", "buildozer.spec", "android_recipes/pygame/__init__.py", "levels/level100.json"}
    if not needed.issubset(archive.namelist()):
        raise RuntimeError("ZIP eski veya eksik. tools/make_apk_zip.py ile güncel paketi oluşturun.")
    for member in archive.infolist():
        if not (target_dir / member.filename).resolve().is_relative_to(target_dir):
            raise RuntimeError("Geçersiz ZIP dosya yolu.")
    archive.extractall(target_dir)
os.chdir(target_dir)
print("Derlenecek proje:", target_dir)
'''), cell("markdown", "## 3. Derle ve başarılı APK'yı indir"), cell("code", '''
import subprocess
from pathlib import Path
from google.colab import files

if not Path("android_recipes/pygame/__init__.py").is_file():
    raise RuntimeError("Önce güncel ZIP dosyasını ikinci adımda yükleyin.")
log_path = Path("build-apk.log")
with log_path.open("w", encoding="utf-8") as log:
    process = subprocess.Popen(["buildozer", "-v", "android", "debug"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    for line in process.stdout:
        print(line, end="")
        log.write(line)
    returncode = process.wait()
if returncode:
    raise RuntimeError(f"Derleme başarısız (kod {returncode}). Tam kayıt: {log_path.resolve()}")
apks = sorted(Path("bin").glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
if not apks:
    raise RuntimeError("Derleme tamamlandı ancak bin/ içinde APK bulunamadı.")
print("APK hazır:", apks[0], "Boyut:", apks[0].stat().st_size, "bayt")
files.download(str(apks[0]))
''')]

notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"},
           "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 0}
for item in cells:
    if item["cell_type"] == "code":
        compile("".join(item["source"]), "colab-cell", "exec")
(ROOT / "HOLO_APK_OLUSTURUCU.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print("Colab notebook generated and syntax checked.")
