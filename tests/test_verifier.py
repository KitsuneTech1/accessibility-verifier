"""
Unit tests for accessibility-verifier.
Tests reporting, analysis functions, and HTML generation.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import accessibility_verifier as av


class TestAccessibilityVerifier(unittest.TestCase):

    def test_analyze_keyboard_reachability_basic(self):
        """Test keyboard reachability analysis returns a report."""
        report = av.analyze_keyboard_reachability("Test Window")

        self.assertIn("window", report)
        self.assertEqual(report["window"], "Test Window")
        self.assertIn("keyboard_accessible_elements", report)
        self.assertIn("warnings", report)

    def test_analyze_focus_order_basic(self):
        """Test focus order analysis returns a report."""
        report = av.analyze_focus_order("Test Window")

        self.assertIn("window", report)
        self.assertIn("focus_order_elements", report)
        self.assertIn("tab_trap_detected", report)
        self.assertIsInstance(report["tab_trap_detected"], bool)

    def test_analyze_visible_focus_basic(self):
        """Test visible focus analysis returns a report."""
        report = av.analyze_visible_focus("Test Window")

        self.assertIn("window", report)
        self.assertIn("visible_focus_detected", report)
        self.assertIn("screenshot_captured", report)

    def test_capture_window_state_missing_window(self):
        """Test capture handles missing window gracefully."""
        result = av.capture_window_state("NonexistentWindow12345")
        # Should return None or empty bytes on failure
        self.assertTrue(result is None or len(result) == 0)

    def test_generate_html_report_creates_file(self):
        """Test HTML report generation creates a file."""
        keyboard_report = {"window": "test", "keyboard_accessible_elements": [], "warnings": []}
        focus_order_report = {"window": "test", "focus_order_elements": [], "warnings": []}
        focus_visibility_report = {"window": "test", "warnings": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.html")
            result = av.generate_html_report(
                "TestWindow",
                keyboard_report,
                focus_order_report,
                focus_visibility_report,
                output_path
            )

            self.assertEqual(result, output_path)
            self.assertTrue(os.path.exists(output_path))

            with open(output_path) as f:
                content = f.read()

            self.assertIn("TestWindow", content)
            self.assertIn("Accessibility", content)
            self.assertIn("html", content.lower())

    def test_generate_html_report_includes_warnings(self):
        """Test HTML report includes warnings."""
        keyboard_report = {
            "window": "test",
            "keyboard_accessible_elements": [],
            "warnings": ["Test warning 1"]
        }
        focus_order_report = {
            "window": "test",
            "focus_order_elements": [],
            "warnings": ["Test warning 2"]
        }
        focus_visibility_report = {
            "window": "test",
            "warnings": ["Test warning 3"]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.html")
            av.generate_html_report(
                "TestWindow",
                keyboard_report,
                focus_order_report,
                focus_visibility_report,
                output_path
            )

            with open(output_path) as f:
                content = f.read()

            self.assertIn("Test warning 1", content)
            self.assertIn("Test warning 2", content)
            self.assertIn("Test warning 3", content)

    def test_cli_argument_parsing(self):
        """Test CLI argument parsing."""
        args = av.parse_args(["MyWindow", "--output", "custom_report.html", "--snap", "custom_snap.exe"])

        self.assertEqual(args.window, "MyWindow")
        self.assertEqual(args.output, "custom_report.html")
        self.assertEqual(args.snap, "custom_snap.exe")
        self.assertFalse(args.json)

    def test_cli_argument_parsing_json(self):
        """Test CLI JSON flag parsing."""
        args = av.parse_args(["MyWindow", "--json"])

        self.assertEqual(args.window, "MyWindow")
        self.assertTrue(args.json)

    def test_find_window_by_name_ctypes(self):
        """Test window finding requires ctypes."""
        if av._HAS_CTYPES:
            # This may return None if window doesn't exist, which is fine
            result = av.find_window_by_name("Nonexistent Window 12345 XYZ")
            # Should return None or int, not raise
            self.assertTrue(result is None or isinstance(result, int))

    def test_analyze_all_reports_have_warnings(self):
        """Test that all analyses include warnings (since full UI Automation isn't available)."""
        keyboard_report = av.analyze_keyboard_reachability("test")
        focus_order_report = av.analyze_focus_order("test")
        focus_visibility_report = av.analyze_visible_focus("test")

        self.assertTrue(len(keyboard_report.get("warnings", [])) > 0)
        self.assertTrue(len(focus_order_report.get("warnings", [])) > 0)
        self.assertTrue(len(focus_visibility_report.get("warnings", [])) > 0)


if __name__ == "__main__":
    unittest.main()
