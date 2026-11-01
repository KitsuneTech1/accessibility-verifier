"""
Read-only accessibility checks for a Windows application.

The UI Automation reader is optional because this project has no required
third-party dependencies. The snapshot command is also external and is never
used to send input or activate a window.
"""

import argparse
import hashlib
import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


__version__ = "0.1.0"


from ctypes import wintypes

try:
    from ctypes import windll

    _HAS_CTYPES = True
except ImportError:
    _HAS_CTYPES = False


_CONTROL_TYPE_NAMES = {
    50000: "Button",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50007: "ListItem",
    50008: "List",
    50011: "MenuItem",
    50013: "RadioButton",
    50015: "Slider",
    50016: "Spinner",
    50019: "TabItem",
    50021: "TreeItem",
}
_INTERACTIVE_CONTROL_TYPES = set(_CONTROL_TYPE_NAMES) - {50007}


def find_window_by_name(window_name: str) -> Optional[int]:
    """Return a top-level window handle without activating the window."""
    if not _HAS_CTYPES:
        return None

    try:
        find_window = windll.user32.FindWindowW
        find_window.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        find_window.restype = wintypes.HWND
        hwnd = find_window(None, window_name)
        return hwnd or None
    except Exception:
        return None


def capture_window_state(window_name: str, snap_cmd: str = "snap.exe") -> Optional[bytes]:
    """Capture a window through an external, read-only snapshot command.

    The temporary output file is removed on both success and failure. The
    command is passed the window title and is not asked to activate it.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [snap_cmd, "--window", window_name, "--output", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not os.path.exists(tmp_path):
            return None

        with open(tmp_path, "rb") as snapshot:
            return snapshot.read()
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _safe_attribute(element, name: str, default=None):
    try:
        return getattr(element, name)
    except Exception:
        return default


def _rectangle_value(rectangle, name: str) -> Optional[int]:
    value = _safe_attribute(rectangle, name)
    return int(value) if value is not None else None


def _element_record(element, order: int) -> Dict:
    """Convert a comtypes UI Automation element to plain testable data."""
    control_type = _safe_attribute(element, "CurrentControlType")
    rectangle = _safe_attribute(element, "CurrentBoundingRectangle")
    record = {
        "order": order,
        "name": _safe_attribute(element, "CurrentName", "") or "",
        "control_type": _CONTROL_TYPE_NAMES.get(control_type, str(control_type or "Unknown")),
        "control_type_id": control_type,
        "automation_id": _safe_attribute(element, "CurrentAutomationId", "") or "",
        "class_name": _safe_attribute(element, "CurrentClassName", "") or "",
        "is_enabled": _safe_attribute(element, "CurrentIsEnabled"),
        "is_keyboard_focusable": _safe_attribute(element, "CurrentIsKeyboardFocusable"),
        "has_keyboard_focus": _safe_attribute(element, "CurrentHasKeyboardFocus", False),
    }
    if rectangle is not None:
        record["bounds"] = {
            "left": _rectangle_value(rectangle, "left"),
            "top": _rectangle_value(rectangle, "top"),
            "right": _rectangle_value(rectangle, "right"),
            "bottom": _rectangle_value(rectangle, "bottom"),
        }
    return record


def _enumerate_with_comtypes(hwnd: int) -> List[Dict]:
    """Read descendants in UI Automation tree order using optional comtypes."""
    from comtypes.client import CreateObject

    automation = CreateObject("UIAutomationClient.CUIAutomation8")
    root = automation.ElementFromHandle(hwnd)
    condition = automation.CreateTrueCondition()
    descendants = root.FindAll(4, condition)  # TreeScope_Descendants
    return [
        _element_record(descendants.GetElement(index), index + 1)
        for index in range(descendants.Length)
    ]


def _normalise_provider_record(record, order: int) -> Dict:
    if isinstance(record, dict):
        normalised = dict(record)
    else:
        normalised = _element_record(record, order)
    normalised.setdefault("order", order)
    control_type = normalised.get("control_type")
    if isinstance(control_type, int):
        normalised["control_type"] = _CONTROL_TYPE_NAMES.get(control_type, str(control_type))
    if "is_enabled" not in normalised:
        normalised["is_enabled"] = True
    if "is_keyboard_focusable" not in normalised:
        normalised["is_keyboard_focusable"] = False
    if "has_keyboard_focus" not in normalised:
        normalised["has_keyboard_focus"] = False
    return normalised


def _read_ui_automation(
    window_name: str, ui_provider=None
) -> Tuple[Optional[int], List[Dict], List[str]]:
    hwnd = find_window_by_name(window_name)
    if hwnd is None:
        return None, [], [f"Could not find window: {window_name}"]

    try:
        if ui_provider is None:
            raw_elements = _enumerate_with_comtypes(hwnd)
        elif callable(ui_provider):
            raw_elements = ui_provider(hwnd)
        else:
            raw_elements = ui_provider.enumerate(hwnd)
        elements = [
            _normalise_provider_record(record, index + 1)
            for index, record in enumerate(raw_elements or [])
        ]
        return hwnd, elements, []
    except ImportError:
        return hwnd, [], [
            "UI Automation is unavailable because optional dependency 'comtypes' is not installed."
        ]
    except Exception as exc:
        return hwnd, [], [f"UI Automation check failed: {exc}"]


def _is_interactive(element: Dict) -> bool:
    if "is_interactive" in element:
        return bool(element["is_interactive"])
    control_type = element.get("control_type_id")
    if isinstance(control_type, int):
        return control_type in _INTERACTIVE_CONTROL_TYPES
    return element.get("control_type") in {
        _CONTROL_TYPE_NAMES[type_id] for type_id in _INTERACTIVE_CONTROL_TYPES
    }


def analyze_keyboard_reachability(window_name: str, ui_provider=None) -> Dict:
    """List enabled interactive controls and whether UIA marks them focusable."""
    report = {
        "window": window_name,
        "ui_automation_available": False,
        "keyboard_accessible_elements": [],
        "keyboard_inaccessible_elements": [],
        "keyboard_traps": [],
        "warnings": [],
    }
    _, elements, warnings = _read_ui_automation(window_name, ui_provider)
    report["warnings"].extend(warnings)
    if warnings:
        return report

    report["ui_automation_available"] = True
    for element in elements:
        if not element.get("is_enabled", True) or not _is_interactive(element):
            continue
        if element.get("is_keyboard_focusable"):
            report["keyboard_accessible_elements"].append(element)
        else:
            report["keyboard_inaccessible_elements"].append(element)

    if report["keyboard_inaccessible_elements"]:
        report["warnings"].append(
            "Some enabled interactive controls are not marked keyboard-focusable by UI Automation."
        )
    report["warnings"].append(
        "Tab traps are not tested because this tool never sends keyboard input."
    )
    return report


def analyze_focus_order(window_name: str, ui_provider=None) -> Dict:
    """Report focusable controls in UI Automation tree order.

    UI Automation does not expose a portable, guaranteed Tab sequence for every
    framework. The result is therefore an observed tree order, not a simulated
    Tab run.
    """
    report = {
        "window": window_name,
        "ui_automation_available": False,
        "focus_order_elements": [],
        "potential_issues": [],
        "tab_trap_detected": None,
        "tab_trap_status": "not_tested",
        "warnings": [],
    }
    _, elements, warnings = _read_ui_automation(window_name, ui_provider)
    report["warnings"].extend(warnings)
    if warnings:
        return report

    report["ui_automation_available"] = True
    report["focus_order_elements"] = [
        element
        for element in elements
        if element.get("is_enabled", True) and element.get("is_keyboard_focusable")
    ]
    if not report["focus_order_elements"]:
        report["potential_issues"].append("No enabled keyboard-focusable elements were found.")
    report["warnings"].append(
        "Focus order is the UI Automation tree order. A real Tab sequence is not tested."
    )
    report["warnings"].append(
        "Tab traps are not tested because this tool never sends keyboard input."
    )
    return report


def analyze_visible_focus(
    window_name: str,
    snap_cmd: str = "snap.exe",
    snapshot_path: Optional[str] = None,
    ui_provider=None,
) -> Dict:
    """Capture the window and identify any UIA element reporting keyboard focus.

    A screenshot alone cannot prove that a focus indicator is visible. The
    report consequently leaves ``visible_focus_detected`` unknown and asks for
    manual review of the saved capture.
    """
    report = {
        "window": window_name,
        "visible_focus_detected": None,
        "focus_indicator_status": "manual_review",
        "focused_elements": [],
        "screenshot_captured": False,
        "warnings": [],
    }

    _, elements, warnings = _read_ui_automation(window_name, ui_provider)
    report["warnings"].extend(warnings)
    report["focused_elements"] = [
        element for element in elements if element.get("has_keyboard_focus")
    ]
    if not report["focused_elements"] and not warnings:
        report["warnings"].append("UI Automation did not report a focused descendant.")

    png_data = capture_window_state(window_name, snap_cmd)
    if png_data:
        report["screenshot_captured"] = True
        report["screenshot_size"] = len(png_data)
        report["screenshot_sha256"] = hashlib.sha256(png_data).hexdigest()
        if snapshot_path:
            try:
                Path(snapshot_path).write_bytes(png_data)
                report["screenshot_path"] = str(snapshot_path)
            except OSError as exc:
                report["warnings"].append(f"Could not save screenshot: {exc}")
    else:
        report["warnings"].append(
            f"Could not capture window with '{snap_cmd}'. Install or provide a working snapshot command."
        )

    report["warnings"].append(
        "A screenshot cannot establish visible focus automatically. Inspect the capture manually."
    )
    return report


def _display_element(element: Dict) -> str:
    if not isinstance(element, dict):
        return str(element)
    name = element.get("name") or "Unnamed element"
    control_type = element.get("control_type") or "element"
    return f"{name} ({control_type})"


def _snapshot_link(snapshot_path: str, report_path: str) -> str:
    """Return a browser-relative snapshot path for the generated report."""
    try:
        report_directory = Path(report_path).resolve().parent
        snapshot = Path(snapshot_path).resolve()
        return Path(os.path.relpath(snapshot, report_directory)).as_posix()
    except (OSError, ValueError):
        return Path(snapshot_path).name


def _warning_blocks(warnings: Iterable[str]) -> str:
    return "".join(
        f'        <div class="warning">{html.escape(str(warning))}</div>\n'
        for warning in warnings
    )


def generate_html_report(
    window_name: str,
    keyboard_report: Dict,
    focus_order_report: Dict,
    focus_visibility_report: Dict,
    output_path: str = "accessibility_report.html",
) -> str:
    """Write an HTML report with escaped findings and explicit limitations."""
    escaped_window = html.escape(str(window_name))
    keyboard_items = "".join(
        f"            <li>{html.escape(_display_element(element))}</li>\n"
        for element in keyboard_report.get("keyboard_accessible_elements", [])
    )
    inaccessible_items = "".join(
        f"            <li>{html.escape(_display_element(element))}</li>\n"
        for element in keyboard_report.get("keyboard_inaccessible_elements", [])
    )
    focus_items = "".join(
        f"            <li>{html.escape(_display_element(element))}</li>\n"
        for element in focus_order_report.get("focus_order_elements", [])
    )
    focused_items = "".join(
        f"            <li>{html.escape(_display_element(element))}</li>\n"
        for element in focus_visibility_report.get("focused_elements", [])
    )
    screenshot = ""
    screenshot_path = focus_visibility_report.get("screenshot_path")
    if screenshot_path:
        snapshot_link = _snapshot_link(screenshot_path, output_path)
        screenshot = (
            f'        <p><img src="{html.escape(snapshot_link)}" '
            "alt=\"Captured window for manual focus review\"></p>\n"
        )
    empty_keyboard = "            <li>None observed</li>\n"
    empty_focus = "            <li>None observed</li>\n"
    keyboard_items_html = keyboard_items or empty_keyboard
    inaccessible_items_html = inaccessible_items or empty_keyboard
    focus_items_html = focus_items or empty_focus
    focused_items_html = focused_items or empty_focus

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Accessibility Report - {escaped_window}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.4; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; border-bottom: 2px solid #ddd; padding-bottom: 8px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #007acc; }}
        .warning {{ color: #7a1f1f; background: #fff3cd; padding: 8px; margin: 8px 0; }}
        .good {{ color: #245b24; background: #dff0d8; padding: 8px; margin: 8px 0; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>Accessibility Verification Report</h1>
    <p>Window: <strong>{escaped_window}</strong></p>
    <p>Generated with accessibility-verifier v{__version__}</p>

    <div class="section">
        <h2>Keyboard Reachability</h2>
        <p>Enabled interactive controls marked keyboard-focusable by UI Automation:</p>
        <ul>{keyboard_items_html}        </ul>
        <p>Enabled interactive controls not marked keyboard-focusable:</p>
        <ul>{inaccessible_items_html}        </ul>
{_warning_blocks(keyboard_report.get("warnings", []))}    </div>

    <div class="section">
        <h2>Focus Order</h2>
        <p>Focusable controls in UI Automation tree order:</p>
        <ol>{focus_items_html}        </ol>
        <p>Tab trap status: <strong>{html.escape(str(focus_order_report.get("tab_trap_status", "not_tested")))}</strong></p>
{_warning_blocks(focus_order_report.get("warnings", []))}    </div>

    <div class="section">
        <h2>Visible Focus</h2>
        <p>UI Automation reported focused descendants:</p>
        <ul>{focused_items_html}        </ul>
        <p>Visible focus result: <strong>Manual review required</strong></p>
""" + (
        '        <div class="good">Screenshot captured for manual inspection.</div>\n'
        if focus_visibility_report.get("screenshot_captured")
        else '        <div class="warning">No screenshot was captured.</div>\n'
    ) + f"""{screenshot}{_warning_blocks(focus_visibility_report.get("warnings", []))}    </div>

    <div class="section">
        <h2>Scope</h2>
        <p>This tool reads window and UI Automation state. It never activates a window or sends keyboard or mouse input.</p>
        <p>Focus order is not a simulated Tab run, and visible focus cannot be proven from one screenshot without manual review.</p>
    </div>
</body>
</html>
"""

    Path(output_path).write_text(html_content, encoding="utf-8")
    return output_path


def parse_args(args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Read-only Windows accessibility checks for keyboard and focus state."
    )
    parser.add_argument("window", help="Target window title")
    parser.add_argument(
        "--output", default="accessibility_report.html", help="HTML report path"
    )
    parser.add_argument(
        "--snap", default="snap.exe", help="Read-only snapshot command (default: snap.exe)"
    )
    parser.add_argument(
        "--snapshot-output",
        help="PNG path for the captured window (default: report path with .png suffix)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the combined report as JSON"
    )
    return parser.parse_args(args)


def main():
    """CLI entrypoint."""
    args = parse_args()
    print(f"Analyzing accessibility for: {args.window}", file=sys.stderr)
    snapshot_path = args.snapshot_output or str(Path(args.output).with_suffix(".png"))

    keyboard_report = analyze_keyboard_reachability(args.window)
    focus_order_report = analyze_focus_order(args.window)
    focus_visibility_report = analyze_visible_focus(
        args.window, snap_cmd=args.snap, snapshot_path=snapshot_path
    )
    combined = {
        "window": args.window,
        "keyboard_reachability": keyboard_report,
        "focus_order": focus_order_report,
        "visible_focus": focus_visibility_report,
    }

    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        report_path = generate_html_report(
            args.window,
            keyboard_report,
            focus_order_report,
            focus_visibility_report,
            args.output,
        )
        print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
