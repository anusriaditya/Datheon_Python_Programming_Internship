# 🚀 Autonomous Desktop File Organiser & Cleanup Utility

An autonomous, cross-platform desktop automation utility designed to declutter messy directories (such as `Downloads`, `Desktop`, or shared folders). The script scans files, dynamically creates structured category subdirectories, and relocates items safely while handling naming collisions, system files, and permission constraints.

---

## 🌟 Key Features

- **📂 Dynamic Categorization**: Automatically categorizes files by extension into dedicated subfolders (`/Documents`, `/Images`, `/Videos`, `/Audio`, `/Archives`, `/Code`, `/Executables`, `/Others`).
- **🛡️ Collision-Safe Relocation**: Automatically detects when a file with the same name already exists in the target category folder and resolves the collision using non-destructive incremental naming (e.g., `report (1).pdf`, `report (2).pdf`).
- **🔒 Robust Exception & Lock Handling**:
  - Catches `PermissionError` (e.g., locked files in use by Word, Excel, or another background process).
  - Catches `FileExistsError` and `shutil.Error`.
- **🚫 Intelligent Skip Filters**:
  - Skips active and partial downloads (`.crdownload`, `.part`, `.tmp`, `.download`).
  - Skips temporary Office lock files (e.g., `~$document.docx`).
  - Skips system files (`desktop.ini`, `thumbs.db`, `.DS_Store`).
  - Skips the organizer script itself and subdirectories to avoid nested loops.
- **🔍 Dry-Run Mode (`--dry-run`)**: Allows you to simulate reorganization and preview every file move without touching disk files.
- **⏱️ Autonomous Background Mode (`--watch`)**: Runs continuously as a background daemon/polling watcher (configurable interval) to automatically clean up new downloads as they arrive.
- **📊 Formatted Execution Summary**: Displays an ASCII table summarizing files scanned, relocated per category, collisions resolved, skipped, and execution elapsed time.

---

## 📁 Default Category Mappings

| Category | File Extensions |
| :--- | :--- |
| **Documents** | `.pdf`, `.docx`, `.doc`, `.txt`, `.rtf`, `.odt`, `.xlsx`, `.xls`, `.csv`, `.pptx`, `.ppt`, `.epub`, `.md`, etc. |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.svg`, `.webp`, `.tiff`, `.ico`, `.raw`, `.heic`, `.psd`, etc. |
| **Videos** | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, etc. |
| **Audio** | `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.m4a`, `.wma`, `.midi`, etc. |
| **Archives** | `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`, `.iso`, `.tgz` |
| **Code** | `.py`, `.js`, `.ts`, `.html`, `.css`, `.java`, `.c`, `.cpp`, `.cs`, `.json`, `.xml`, `.yaml`, `.sh`, `.bat`, `.ps1`, `.sql`, etc. |
| **Executables**| `.exe`, `.msi`, `.apk`, `.dmg`, `.pkg`, `.deb`, `.rpm` |
| **Others** | (Optional via `--move-unknown`) Any unrecognized file types |

---

## 🛠️ Installation & Requirements

- **Python 3.8+** (Zero third-party dependencies; uses only Python Standard Library modules: `os`, `shutil`, `argparse`, `pathlib`, `time`, etc.).

---

## 💻 Usage & CLI Guide

### 1. Organize Current Directory
```bash
python organizer.py
```

### 2. Organize a Specific Folder (e.g., Downloads)
```bash
python organizer.py --path "C:\Users\<YourUser>\Downloads"
```
*(On macOS / Linux: `python organizer.py --path "~/Downloads"`)*

### 3. Dry-Run Mode (Preview Only)
Simulate the cleanup without actually moving any files:
```bash
python organizer.py --path "C:\Users\<YourUser>\Downloads" --dry-run
```

### 4. Continuous Autonomous Watch Mode
Run in the background, checking and organizing every 10 seconds:
```bash
python organizer.py --path "C:\Users\<YourUser>\Downloads" --watch --interval 10
```

### 5. Categorize Unrecognized Extensions
Move any unrecognized file extension into an `Others/` folder:
```bash
python organizer.py --move-unknown
```

---

## 📋 CLI Argument Reference

| Flag | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--path` | `-p` | Target directory to organize | `.` (Current directory) |
| `--dry-run` | `-n` | Preview actions without moving files | `False` |
| `--watch` | `-w` | Autonomous mode: loop continuously | `False` |
| `--interval` | `-i` | Polling interval in seconds for `--watch` | `10` |
| `--move-unknown`| | Relocate unrecognized extensions | `False` (Leaves untouched) |
| `--unknown-folder` | | Custom folder name for unrecognized files | `Others` |
| `--help` | `-h` | Display help and usage examples | |

---

## 🧪 Running Unit & Integration Tests

The test suite covers file placement, collision resolution, temporary file skipping, directory exclusion, dry-run simulation, permission exceptions, and locked file detection:

```bash
python -m unittest test_organizer.py
```

---

## 🛡️ Safety & Reliability Considerations

1. **Non-Destructive Overwrites**: If `invoice.pdf` already exists in `Documents/`, the utility automatically calculates `invoice (1).pdf`, avoiding accidental overwriting or data loss.
2. **Locked File Detection**: On Windows, files currently open in applications (such as Word or media players) are tested before moving to prevent partial move errors.
3. **In-Progress Download Protection**: Browsers like Chrome, Firefox, and Edge create `.crdownload` or `.part` files while downloading. These files are skipped until the download finishes.
