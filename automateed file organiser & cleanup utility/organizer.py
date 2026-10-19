#!/usr/bin/env python3
"""
Automated File Organiser & Cleanup Utility
==========================================
An autonomous desktop automation utility that organizes cluttered directories
(e.g., Downloads, Desktop) by categorizing files into dedicated subfolders based
on file extensions, safely handling naming collisions, and gracefully recovering
from permission or OS errors.

Features:
- Dynamic category folder creation (/Documents, /Images, /Videos, /Archives, /Code, etc.)
- Collision-safe moving: automatically resolves naming conflicts using incremental naming (e.g. 'file (1).pdf')
- Safe exception handling for PermissionError (e.g., file open in another app) and FileExistsError
- Skip rules for temporary/download files (.tmp, .crdownload, ~$office lock files) and the script itself
- Dry-run mode (--dry-run) to preview changes without modifying files
- Autonomous monitoring mode (--watch) to automatically organize incoming files continuously
- Formatted execution summary table with statistics
"""

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Default extension to category folder mapping
DEFAULT_EXTENSION_MAP: Dict[str, str] = {
    # Documents
    '.pdf': 'Documents',
    '.doc': 'Documents',
    '.docx': 'Documents',
    '.txt': 'Documents',
    '.rtf': 'Documents',
    '.odt': 'Documents',
    '.xlsx': 'Documents',
    '.xls': 'Documents',
    '.csv': 'Documents',
    '.pptx': 'Documents',
    '.ppt': 'Documents',
    '.epub': 'Documents',
    '.mobi': 'Documents',
    '.tsv': 'Documents',
    '.md': 'Documents',

    # Images
    '.jpg': 'Images',
    '.jpeg': 'Images',
    '.png': 'Images',
    '.gif': 'Images',
    '.bmp': 'Images',
    '.svg': 'Images',
    '.webp': 'Images',
    '.tiff': 'Images',
    '.tif': 'Images',
    '.ico': 'Images',
    '.raw': 'Images',
    '.heic': 'Images',
    '.psd': 'Images',
    '.ai': 'Images',

    # Videos
    '.mp4': 'Videos',
    '.mkv': 'Videos',
    '.avi': 'Videos',
    '.mov': 'Videos',
    '.wmv': 'Videos',
    '.flv': 'Videos',
    '.webm': 'Videos',
    '.m4v': 'Videos',
    '.3gp': 'Videos',
    '.mpeg': 'Videos',
    '.mpg': 'Videos',

    # Audio
    '.mp3': 'Audio',
    '.wav': 'Audio',
    '.flac': 'Audio',
    '.aac': 'Audio',
    '.ogg': 'Audio',
    '.m4a': 'Audio',
    '.wma': 'Audio',
    '.mid': 'Audio',
    '.midi': 'Audio',

    # Archives
    '.zip': 'Archives',
    '.rar': 'Archives',
    '.7z': 'Archives',
    '.tar': 'Archives',
    '.gz': 'Archives',
    '.bz2': 'Archives',
    '.xz': 'Archives',
    '.iso': 'Archives',
    '.tgz': 'Archives',

    # Code & Scripts
    '.py': 'Code',
    '.js': 'Code',
    '.ts': 'Code',
    '.html': 'Code',
    '.htm': 'Code',
    '.css': 'Code',
    '.scss': 'Code',
    '.java': 'Code',
    '.c': 'Code',
    '.cpp': 'Code',
    '.h': 'Code',
    '.hpp': 'Code',
    '.cs': 'Code',
    '.json': 'Code',
    '.xml': 'Code',
    '.yaml': 'Code',
    '.yml': 'Code',
    '.sh': 'Code',
    '.bat': 'Code',
    '.ps1': 'Code',
    '.sql': 'Code',
    '.php': 'Code',
    '.rb': 'Code',
    '.rs': 'Code',
    '.go': 'Code',

    # Executables & Installers
    '.exe': 'Executables',
    '.msi': 'Executables',
    '.apk': 'Executables',
    '.dmg': 'Executables',
    '.pkg': 'Executables',
    '.deb': 'Executables',
    '.rpm': 'Executables',
}

# Ignored extensions (temporary or partial downloads)
TEMPORARY_EXTENSIONS: Set[str] = {
    '.crdownload',
    '.part',
    '.partial',
    '.tmp',
    '.temp',
    '.download',
}

# System files to ignore
SYSTEM_FILENAMES: Set[str] = {
    'desktop.ini',
    'thumbs.db',
    '.ds_store',
}


@dataclass
class OrganizeStats:
    """Tracks metrics and statistics for an organization session."""
    total_scanned: int = 0
    total_moved: int = 0
    collisions_resolved: int = 0
    errors: int = 0
    skipped: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    error_details: List[str] = field(default_factory=list)
    elapsed_time: float = 0.0


def is_file_in_use(file_path: Path) -> bool:
    """
    Check if a file is currently locked/opened by another process (Windows check).
    Attempts to rename or open in append mode to test lock.
    """
    if not file_path.exists():
        return False
    try:
        # Try opening in append mode to test if file is locked for writing
        with open(file_path, 'r+b'):
            pass
        return False
    except (PermissionError, OSError):
        return True


def resolve_collision(target_dir: Path, original_filename: str) -> Tuple[Path, bool]:
    """
    Resolves naming collisions in the target directory by appending
    an incrementing index: 'name (1).ext', 'name (2).ext', etc.

    Returns:
        Tuple[Path, bool]: (resolved_destination_path, collision_occurred)
    """
    target_path = target_dir / original_filename
    if not target_path.exists():
        return target_path, False

    source_path = Path(original_filename)
    stem = source_path.stem
    suffix = source_path.suffix

    counter = 1
    while True:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = target_dir / candidate_name
        if not candidate_path.exists():
            return candidate_path, True
        counter += 1


class FileOrganizer:
    """Autonomous File Organiser engine."""

    def __init__(
        self,
        target_directory: Path,
        extension_map: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
        move_unknown: bool = False,
        unknown_category: str = "Others",
        ignored_names: Optional[Set[str]] = None,
    ):
        self.target_dir = target_directory.resolve()
        self.extension_map = extension_map or DEFAULT_EXTENSION_MAP
        self.dry_run = dry_run
        self.move_unknown = move_unknown
        self.unknown_category = unknown_category
        self.ignored_names = ignored_names or set()

        # Add this script's name and common system files to ignore list
        current_script = Path(__file__).resolve().name.lower()
        self.ignored_names.add(current_script)
        for sys_file in SYSTEM_FILENAMES:
            self.ignored_names.add(sys_file.lower())

        # Keep a set of known category folders so we don't treat them as files
        self.category_names = set(self.extension_map.values())
        if self.move_unknown:
            self.category_names.add(self.unknown_category)

    def should_skip(self, entry: os.DirEntry) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a directory entry should be skipped.

        Returns:
            Tuple[bool, Optional[str]]: (should_skip, reason)
        """
        # We only organize files directly inside target directory
        if not entry.is_file(follow_symlinks=False):
            return True, "Not a regular file (directory or symlink)"

        name_lower = entry.name.lower()

        # Skip ignored filenames (system files, script itself)
        if name_lower in self.ignored_names:
            return True, f"Ignored system file or script: {entry.name}"

        # Skip hidden files
        if entry.name.startswith('.'):
            return True, f"Hidden file: {entry.name}"

        # Skip Office temporary lock files (~$filename)
        if entry.name.startswith('~$'):
            return True, f"Office lock file: {entry.name}"

        # Check file extension
        suffix = Path(entry.name).suffix.lower()

        # Skip active temporary/incomplete download files
        if suffix in TEMPORARY_EXTENSIONS:
            return True, f"Incomplete or temporary download: {suffix}"

        # Check if category is known or unknown handling is disabled
        category = self.extension_map.get(suffix)
        if not category and not self.move_unknown:
            return True, f"Unrecognized extension '{suffix}' and move_unknown is False"

        return False, None

    def organize(self, verbose: bool = True) -> OrganizeStats:
        """
        Scans target directory using os.scandir() and relocates files using shutil.move().
        """
        stats = OrganizeStats()
        start_time = time.perf_counter()

        if not self.target_dir.exists():
            raise FileNotFoundError(f"Target directory does not exist: {self.target_dir}")

        if not self.target_dir.is_dir():
            raise NotADirectoryError(f"Target path is not a directory: {self.target_dir}")

        if verbose:
            mode_label = "[DRY-RUN] " if self.dry_run else ""
            print(f"\n{mode_label}Scanning directory: {self.target_dir}\n" + "-" * 60)

        try:
            with os.scandir(self.target_dir) as entries:
                for entry in entries:
                    try:
                        stats.total_scanned += 1
                        skip, reason = self.should_skip(entry)
                        if skip:
                            stats.skipped += 1
                            continue

                        suffix = Path(entry.name).suffix.lower()
                        category = self.extension_map.get(suffix, self.unknown_category)

                        category_dir = self.target_dir / category

                        # Safely compute collision-free destination
                        destination_path, collision = resolve_collision(category_dir, entry.name)
                        if collision:
                            stats.collisions_resolved += 1

                        source_path = Path(entry.path)

                        if self.dry_run:
                            collision_msg = f" (Collision resolved -> '{destination_path.name}')" if collision else ""
                            if verbose:
                                print(f"[DRY-RUN] Would move: '{entry.name}' -> '{category}/{destination_path.name}'{collision_msg}")
                            stats.total_moved += 1
                            stats.category_counts[category] = stats.category_counts.get(category, 0) + 1
                            continue

                        # Perform actual file relocation
                        # 1. Dynamically create category subfolder
                        category_dir.mkdir(parents=True, exist_ok=True)

                        # 2. Check if file is currently open/locked (common on Windows)
                        if is_file_in_use(source_path):
                            err_msg = f"Skipped '{entry.name}': File is in use by another application"
                            stats.errors += 1
                            stats.error_details.append(err_msg)
                            if verbose:
                                print(f"[LOCKED] {err_msg}")
                            continue

                        # 3. Move file with shutil.move
                        shutil.move(str(source_path), str(destination_path))
                        stats.total_moved += 1
                        stats.category_counts[category] = stats.category_counts.get(category, 0) + 1

                        if verbose:
                            collision_msg = f" [Collision -> renamed to '{destination_path.name}']" if collision else ""
                            print(f"[MOVED] '{entry.name}' -> '{category}/{destination_path.name}'{collision_msg}")

                    except PermissionError as pe:
                        stats.errors += 1
                        msg = f"Permission denied for '{entry.name}': {pe}"
                        stats.error_details.append(msg)
                        if verbose:
                            print(f"[ERROR] {msg}")

                    except FileExistsError as fe:
                        stats.errors += 1
                        msg = f"File already exists conflict for '{entry.name}': {fe}"
                        stats.error_details.append(msg)
                        if verbose:
                            print(f"[ERROR] {msg}")

                    except (shutil.Error, OSError) as oe:
                        stats.errors += 1
                        msg = f"OS/Shutil error moving '{entry.name}': {oe}"
                        stats.error_details.append(msg)
                        if verbose:
                            print(f"[ERROR] {msg}")

        except PermissionError as pe:
            stats.errors += 1
            stats.error_details.append(f"Permission denied accessing directory '{self.target_dir}': {pe}")
            if verbose:
                print(f"[CRITICAL] Permission denied accessing directory: {pe}")

        stats.elapsed_time = time.perf_counter() - start_time
        return stats


def print_summary(stats: OrganizeStats, target_dir: Path, dry_run: bool = False) -> None:
    """Prints a nicely formatted execution summary table."""
    mode_str = "DRY-RUN (Simulated)" if dry_run else "LIVE EXECUTION"
    table_width = 62

    print("\n" + "=" * table_width)
    print("       DIRECTORY CLEANUP EXECUTION SUMMARY".center(table_width))
    print("=" * table_width)
    print(f" Target Directory : {target_dir}")
    print(f" Execution Mode   : {mode_str}")
    print(f" Elapsed Time     : {stats.elapsed_time:.4f} seconds")
    print("-" * table_width)
    print(f" {'Category':<30} | {'Files Relocated':>15}")
    print("-" * table_width)

    if stats.category_counts:
        for cat in sorted(stats.category_counts.keys()):
            count = stats.category_counts[cat]
            print(f" /{cat:<29} | {count:>15}")
    else:
        print(f" {'(No files relocated)':<30} | {'0':>15}")

    print("-" * table_width)
    print(f" {'Total Files Scanned':<30} : {stats.total_scanned:>10}")
    print(f" {'Total Files Relocated':<30} : {stats.total_moved:>10}")
    print(f" {'Collisions Resolved':<30} : {stats.collisions_resolved:>10}")
    print(f" {'Files Skipped (Ignored/Temp)':<30} : {stats.skipped:>10}")
    print(f" {'Errors / Permission Denied':<30} : {stats.errors:>10}")
    print("=" * table_width)

    if stats.error_details:
        print("\n[!] Execution Issues Encountered:")
        for err in stats.error_details:
            print(f"  - {err}")
    print()


def run_watch_loop(organizer: FileOrganizer, interval_seconds: int = 10) -> None:
    """Runs the organizer continuously at specified intervals."""
    print(f"\n[AUTONOMOUS MONITORING STARTED]")
    print(f"Monitoring directory: {organizer.target_dir}")
    print(f"Polling interval: {interval_seconds} seconds. Press Ctrl+C to terminate.\n")

    cycle = 1
    try:
        while True:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Cycle #{cycle} checking...")
            stats = organizer.organize(verbose=False)
            if stats.total_moved > 0 or stats.errors > 0:
                print_summary(stats, organizer.target_dir, organizer.dry_run)
            else:
                print(f"[{timestamp}] Directory clean. No new files to relocate.")
            cycle += 1
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[STOPPED] Autonomous monitoring stopped by user.")


def parse_arguments() -> argparse.Namespace:
    """Configures and parses CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Desktop File Organiser & Cleanup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Organize current directory
  python organizer.py

  # Organize Downloads directory
  python organizer.py --path "~/Downloads"

  # Preview actions without moving any files (Dry Run)
  python organizer.py --path "~/Downloads" --dry-run

  # Run autonomously every 15 seconds
  python organizer.py --path "~/Downloads" --watch --interval 15

  # Categorize unknown extensions into /Others
  python organizer.py --move-unknown
        """
    )
    parser.add_argument(
        "-p", "--path",
        type=str,
        default=".",
        help="Target directory to organize (default: current directory)."
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Simulate the cleanup without moving any files."
    )
    parser.add_argument(
        "-w", "--watch",
        action="store_true",
        help="Autonomous mode: continuously monitor and organize directory."
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=10,
        help="Polling interval in seconds for --watch mode (default: 10s)."
    )
    parser.add_argument(
        "--move-unknown",
        action="store_true",
        help="Move files with unrecognized extensions into an 'Others' folder."
    )
    parser.add_argument(
        "--unknown-folder",
        type=str,
        default="Others",
        help="Folder name for unrecognized files if --move-unknown is enabled."
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_arguments()
    target_path = Path(os.path.expanduser(args.path)).resolve()

    if not target_path.exists():
        print(f"Error: Path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not target_path.is_dir():
        print(f"Error: Path '{target_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    organizer = FileOrganizer(
        target_directory=target_path,
        dry_run=args.dry_run,
        move_unknown=args.move_unknown,
        unknown_category=args.unknown_folder,
    )

    if args.watch:
        run_watch_loop(organizer, interval_seconds=args.interval)
    else:
        stats = organizer.organize(verbose=True)
        print_summary(stats, target_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
