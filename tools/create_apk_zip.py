import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP_PATH = os.path.join(ROOT, "holo_apk_source.zip")

EXCLUDE_DIRS = {".venv", "__pycache__", "screenshots", "levelgen", "server", "tools", "legacy", "bin", ".buildozer", ".git", "dist", "build"}
EXCLUDE_EXTS = {".pyc", ".db", ".log", ".tmp"}
EXCLUDE_FILES = {"save_data.json", "save_data.v1.backup.json", "holo_apk_source.zip"}

def make_apk_zip():
    print(f"Creating {ZIP_PATH} ...")
    count = 0
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ROOT):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ROOT)
                
                # Check top-level folder
                parts = rel_path.split(os.sep)
                if parts[0] in EXCLUDE_DIRS:
                    continue
                
                zf.write(full_path, rel_path)
                count += 1
                
    size_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
    print(f"[OK] Successfully created {ZIP_PATH} with {count} files ({size_mb:.2f} MB).")

if __name__ == "__main__":
    make_apk_zip()
