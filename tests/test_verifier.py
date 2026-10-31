"""
Unit tests for accessibility-verifier.
Tests reporting, analysis functions, and HTML generation.
"""

import json
import hashlib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import accessibility_verifier as av


class TestAccessibilityVerifier(unittest.TestCase):

    def output_path(self, name):
        path = Path(__file__).with_name(name)
        if path.exists():
            path.unlink()
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

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
        self.assertIsNone(report["tab_trap_detected"])
        self.assertEqual(report["tab_trap_status"], "not_tested")

    def test_analyze_visible_focus_basic(self):
        """Test visible focus analysis returns a report."""
        report = av.analyze_visible_focus("Test Window")

        self.assertIn("window", report)
        self.assertIn("visible_focus_detected", report)
        self.assertIn("screenshot_captured", report)
        self.assertIsNone(report["visible_focus_detected"])

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

        output_path = self.output_path("_test_report.html")
        result = av.generate_html_report(
            "TestWindow",
            keyboard_report,
            focus_order_report,
            focus_visibility_report,
            str(output_path),
        )

        self.assertEqual(result, str(output_path))
        self.assertTrue(output_path.exists())

        content = output_path.read_text(encoding="utf-8")
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

        output_path = self.output_path("_warning_report.html")
        av.generate_html_report(
            "TestWindow",
            keyboard_report,
            focus_order_report,
            focus_visibility_report,
            str(output_path),
        )

        content = output_path.read_text(encoding="utf-8")
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

    def test_cli_argument_parsing_snapshot_output(self):
        args = av.parse_args(["MyWindow", "--snapshot-output", "capture.png"])

        self.assertEqual(args.snapshot_output, "capture.png")

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

    def test_ui_automation_provider_reports_reachability(self):
        elements = [
            {
                "name": "Save",
                "control_type": "Button",
                "is_enabled": True,
                "is_keyboard_focusable": True,
            },
            {
                "name": "Secret action",
                "control_type": "Button",
                "is_enabled": True,
                "is_keyboard_focusable": False,
            },
            {
                "name": "Disabled action",
                "control_type": "Button",
                "is_enabled": False,
                "is_keyboard_focusable": False,
            },
        ]

        with patch.object(av, "find_window_by_name", return_value=123):
            report = av.analyze_keyboard_reachability("Test Window", lambda hwnd: elements)

        self.assertTrue(report["ui_automation_available"])
        self.assertEqual([item["name"] for item in report["keyboard_accessible_elements"]], ["Save"])
        self.assertEqual(
            [item["name"] for item in report["keyboard_inaccessible_elements"]],
            ["Secret action"],
        )
        self.assertNotIn("Disabled action", str(report))

    def test_focus_order_uses_provider_order_without_claiming_tab_test(self):
        elements = [
            {"name": "First", "control_type": "Edit", "is_enabled": True, "is_keyboard_focusable": True},
            {"name": "Second", "control_type": "Button", "is_enabled": True, "is_keyboard_focusable": True},
        ]

        with patch.object(av, "find_window_by_name", return_value=123):
            report = av.analyze_focus_order("Test Window", lambda hwnd: elements)

        self.assertEqual([item["name"] for item in report["focus_order_elements"]], ["First", "Second"])
        self.assertEqual(report["tab_trap_status"], "not_tested")
        self.assertTrue(any("tree order" in warning for warning in report["warnings"]))

    def test_visible_focus_saves_capture_and_reports_focused_element(self):
        elements = [
            {
                "name": "Save",
                "control_type": "Button",
                "is_enabled": True,
                "is_keyboard_focusable": True,
                "has_keyboard_focus": True,
            }
        ]
        snapshot_path = self.output_path("_test_window.png")
        with patch.object(av, "find_window_by_name", return_value=123), patch.object(
            av, "capture_window_state", return_value=b"png-bytes"
        ):
            report = av.analyze_visible_focus(
                "Test Window",
                snapshot_path=str(snapshot_path),
                ui_provider=lambda hwnd: elements,
            )

        self.assertTrue(report["screenshot_captured"])
        self.assertEqual(report["focused_elements"][0]["name"], "Save")
        self.assertEqual(
            report["screenshot_sha256"], hashlib.sha256(b"png-bytes").hexdigest()
        )
        self.assertEqual(snapshot_path.read_bytes(), b"png-bytes")

    def test_missing_optional_uia_dependency_is_clear(self):
        with patch.object(av, "find_window_by_name", return_value=123), patch.object(
            av, "_enumerate_with_comtypes", side_effect=ImportError
        ):
            report = av.analyze_keyboard_reachability("Test Window")

        self.assertFalse(report["ui_automation_available"])
        self.assertIn("comtypes", report["warnings"][0])

    def test_capture_cleans_temp_file_when_command_is_missing(self):
        fake_temp = MagicMock()
        fake_temp.name = "capture.png"
        fake_context = MagicMock()
        fake_context.__enter__.return_value = fake_temp
        fake_context.__exit__.return_value = False
        with patch.object(av.tempfile, "NamedTemporaryFile", return_value=fake_context), patch.object(
            av.subprocess, "run", side_effect=FileNotFoundError
        ), patch.object(av.os, "unlink") as unlink:
            self.assertIsNone(av.capture_window_state("Test Window"))

        unlink.assert_called_once_with("capture.png")

    def test_html_report_escapes_findings_and_links_snapshot(self):
        keyboard_report = {
            "keyboard_accessible_elements": [{"name": "<Save>", "control_type": "Button"}],
            "keyboard_inaccessible_elements": [],
            "warnings": ["<unsafe warning>"]
        }
        focus_order_report = {
            "focus_order_elements": [],
            "tab_trap_status": "not_tested",
            "warnings": []
        }
        focus_visibility_report = {
            "focused_elements": [],
            "screenshot_captured": True,
            "screenshot_path": "C:/private/window.png",
            "warnings": []
        }

        output_path = self.output_path("_escaped_report.html")
        av.generate_html_report(
            "<Window>",
            keyboard_report,
            focus_order_report,
            focus_visibility_report,
            str(output_path),
        )
        content = output_path.read_text(encoding="utf-8")

        self.assertIn("&lt;Window&gt;", content)
        self.assertIn("&lt;Save&gt;", content)
        self.assertIn("&lt;unsafe warning&gt;", content)
        self.assertNotIn("<unsafe warning>", content)
        self.assertIn('src="window.png"', content)


if __name__ == "__main__":
    unittest.main()
