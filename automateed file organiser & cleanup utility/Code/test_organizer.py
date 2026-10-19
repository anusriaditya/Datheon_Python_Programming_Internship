#!/usr/bin/env python3
"""
Unit and integration tests for organizer.py
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from organizer import (
    DEFAULT_EXTENSION_MAP,
    FileOrganizer,
    OrganizeStats,
    resolve_collision,
)


class TestFileOrganizer(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for each test
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_organizer_"))

    def tearDown(self):
        # Clean up temporary directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_basic_categorization(self):
        """Test that files are placed into their respective category folders."""
        test_files = [
            ("sample.pdf", "Documents"),
            ("notes.txt", "Documents"),
            ("sheet.xlsx", "Documents"),
            ("photo.jpg", "Images"),
            ("icon.png", "Images"),
            ("clip.mp4", "Videos"),
            ("song.mp3", "Audio"),
            ("bundle.zip", "Archives"),
            ("script.py", "Code"),
            ("app.js", "Code"),
        ]

        for filename, _ in test_files:
            file_path = self.test_dir / filename
            file_path.write_text("dummy content")

        organizer = FileOrganizer(self.test_dir)
        stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, len(test_files))
        self.assertEqual(stats.errors, 0)

        for filename, expected_category in test_files:
            dest_file = self.test_dir / expected_category / filename
            self.assertTrue(dest_file.exists(), f"File {dest_file} was not found in {expected_category}")

    def test_naming_collision_resolution(self):
        """Test that existing files in destination are not overwritten, but renamed with (1), (2), etc."""
        doc_dir = self.test_dir / "Documents"
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Existing files in Documents
        (doc_dir / "report.pdf").write_text("existing version 0")
        (doc_dir / "report (1).pdf").write_text("existing version 1")

        # New file to organize
        (self.test_dir / "report.pdf").write_text("new version 2")

        organizer = FileOrganizer(self.test_dir)
        stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 1)
        self.assertEqual(stats.collisions_resolved, 1)

        # The new file should have been renamed to 'report (2).pdf'
        expected_collision_file = doc_dir / "report (2).pdf"
        self.assertTrue(expected_collision_file.exists())
        self.assertEqual(expected_collision_file.read_text(), "new version 2")

        # Verify original files remain untouched
        self.assertEqual((doc_dir / "report.pdf").read_text(), "existing version 0")
        self.assertEqual((doc_dir / "report (1).pdf").read_text(), "existing version 1")

    def test_resolve_collision_utility(self):
        """Test direct resolve_collision function."""
        dest_dir = self.test_dir / "Images"
        dest_dir.mkdir()
        (dest_dir / "photo.png").write_text("dummy")

        new_path, collided = resolve_collision(dest_dir, "photo.png")
        self.assertTrue(collided)
        self.assertEqual(new_path.name, "photo (1).png")

        # If file doesn't exist, no collision
        non_colliding, collided = resolve_collision(dest_dir, "avatar.png")
        self.assertFalse(collided)
        self.assertEqual(non_colliding.name, "avatar.png")

    def test_skip_temporary_and_system_files(self):
        """Test skipping incomplete downloads (.crdownload, .tmp, ~$lock files)."""
        temp_files = [
            "downloading.crdownload",
            "scratch.tmp",
            "video.part",
            "~$resume.docx",
            ".hidden_file",
        ]

        for fname in temp_files:
            (self.test_dir / fname).write_text("temporary data")

        organizer = FileOrganizer(self.test_dir)
        stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 0)
        self.assertEqual(stats.skipped, len(temp_files))

        # Files should still be in root
        for fname in temp_files:
            self.assertTrue((self.test_dir / fname).exists())

    def test_skip_subdirectories(self):
        """Test that existing subdirectories are not moved or touched."""
        sub_folder = self.test_dir / "Documents"
        sub_folder.mkdir()
        nested_file = sub_folder / "already_organized.pdf"
        nested_file.write_text("already organized")

        custom_folder = self.test_dir / "MySpecialFolder"
        custom_folder.mkdir()

        organizer = FileOrganizer(self.test_dir)
        stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 0)
        self.assertTrue(nested_file.exists())
        self.assertTrue(custom_folder.exists())

    def test_dry_run_mode(self):
        """Test that dry-run does not relocate any files."""
        file_to_test = self.test_dir / "preview.pdf"
        file_to_test.write_text("test")

        organizer = FileOrganizer(self.test_dir, dry_run=True)
        stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 1)
        # Verify file is STILL in original location and Documents/ was not created
        self.assertTrue(file_to_test.exists())
        self.assertFalse((self.test_dir / "Documents").exists())

    def test_unknown_extension_handling(self):
        """Test unknown extensions are either skipped or moved depending on move_unknown flag."""
        mystery_file = self.test_dir / "unknown.xyz123"
        mystery_file.write_text("mystery")

        # Default behavior: skip
        org_default = FileOrganizer(self.test_dir, move_unknown=False)
        stats = org_default.organize(verbose=False)
        self.assertEqual(stats.total_moved, 0)
        self.assertTrue(mystery_file.exists())

        # With move_unknown=True: move to Others
        org_move = FileOrganizer(self.test_dir, move_unknown=True, unknown_category="Others")
        stats_move = org_move.organize(verbose=False)
        self.assertEqual(stats_move.total_moved, 1)
        self.assertTrue((self.test_dir / "Others" / "unknown.xyz123").exists())


    def test_permission_error_handling(self):
        """Test graceful recovery when a PermissionError is raised during moving."""
        from unittest.mock import patch

        (self.test_dir / "protected.pdf").write_text("protected content")

        organizer = FileOrganizer(self.test_dir)
        with patch("shutil.move", side_effect=PermissionError("Permission denied: simulated")):
            stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 0)
        self.assertEqual(stats.errors, 1)
        self.assertTrue(any("Permission denied" in err for err in stats.error_details))
        # File should remain in place
        self.assertTrue((self.test_dir / "protected.pdf").exists())

    def test_in_use_file_skipping(self):
        """Test skipping a file when is_file_in_use reports it is locked."""
        from unittest.mock import patch

        (self.test_dir / "busy.docx").write_text("locked content")

        organizer = FileOrganizer(self.test_dir)
        with patch("organizer.is_file_in_use", return_value=True):
            stats = organizer.organize(verbose=False)

        self.assertEqual(stats.total_moved, 0)
        self.assertEqual(stats.errors, 1)
        self.assertTrue(any("in use" in err for err in stats.error_details))
        self.assertTrue((self.test_dir / "busy.docx").exists())

    def test_print_summary_output(self):
        """Test that print_summary formats and prints output cleanly."""
        import io
        from unittest.mock import patch
        from organizer import print_summary

        stats = OrganizeStats(
            total_scanned=10,
            total_moved=8,
            collisions_resolved=2,
            errors=1,
            skipped=1,
            category_counts={"Documents": 5, "Images": 3},
            error_details=["Simulated locked file"],
            elapsed_time=0.0123
        )

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            print_summary(stats, self.test_dir, dry_run=False)
            output = mock_stdout.getvalue()

        self.assertIn("DIRECTORY CLEANUP EXECUTION SUMMARY", output)
        self.assertIn("Documents", output)
        self.assertIn("Images", output)
        self.assertIn("Collisions Resolved", output)
        self.assertIn("Simulated locked file", output)


if __name__ == "__main__":
    unittest.main()
