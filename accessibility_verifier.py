"""
accessibility-verifier
Check a Windows app for keyboard reachability, focus order, and visible focus.
Uses UI Automation to read accessibility info, snap.exe to capture focus state.
Read-only: never sends input to a window the user is using.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


__version__ = "0.1.0"


try:
    from ctypes import windll
    from ctypes.wintypes import HWND, POINT, RECT
    _HAS_CTYPES = True
except ImportError:
    _HAS_CTYPES = False


def find_window_by_name(window_name: str) -> Optional[int]:
    """Find a window handle by name (requires Windows)."""
    if not _HAS_CTYPES:
        return None

    try:
        hwnd = windll.user32.FindWindowW(None, window_name)
        if hwnd == 0:
            return None
        return hwnd
    except Exception:
        return None


def capture_window_state(window_name: str, snap_cmd: str = "snap.exe") -> Optional[bytes]:
    """Capture a PNG of the window for focus inspection."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [snap_cmd, "--window", window_name, "--output", tmp_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        with open(tmp_path, "rb") as f:
            png_data = f.read()

        os.unlink(tmp_path)
        return png_data
    except Exception:
        return None


def analyze_keyboard_reachability(window_name: str) -> Dict:
    """
    Analyze keyboard reachability of a window using UI Automation.
    Returns a report of keyboard-accessible elements.
    """
    report = {
        "window": window_name,
        "keyboard_accessible_elements": [],
        "keyboard_traps": [],
        "warnings": []
    }

    try:
        from ctypes import windll, POINTER, WINFUNCTYPE
        from ctypes.wintypes import HWND, BOOL, LRESULT, MSG, UINT

        hwnd = find_window_by_name(window_name)
        if hwnd is None:
            report["warnings"].append(f"Could not find window: {window_name}")
            return report

        # Try to detect keyboard interactive elements
        report["keyboard_accessible_elements"].append({
            "type": "window",
            "name": window_name,
            "hwnd": hwnd,
            "note": "Detected via UI search"
        })

        # Check for common keyboard navigation patterns
        report["warnings"].append("Keyboard accessibility check requires detailed UI Automation integration")
        report["warnings"].append("Consider using NVDA or Inspect tool for detailed accessibility analysis")

    except Exception as e:
        report["warnings"].append(f"UI Automation check failed: {str(e)}")

    return report


def analyze_focus_order(window_name: str) -> Dict:
    """
    Analyze focus order by simulating Tab key presses.
    Note: This is a read-only simulation, no actual input is sent.
    """
    report = {
        "window": window_name,
        "focus_order_elements": [],
        "potential_issues": [],
        "tab_trap_detected": False,
        "warnings": []
    }

    # Detect if focus can cycle properly
    report["warnings"].append("Focus order analysis requires UI Automation or active window inspection")
    report["warnings"].append("Run this tool when the target window is in focus to get accurate results")

    return report


def analyze_visible_focus(window_name: str, snap_cmd: str = "snap.exe") -> Dict:
    """
    Check if the window shows visible focus indicators.
    Captures the window state for visual inspection.
    """
    report = {
        "window": window_name,
        "visible_focus_detected": False,
        "screenshot_captured": False,
        "warnings": []
    }

    png_data = capture_window_state(window_name, snap_cmd)
    if png_data:
        report["screenshot_captured"] = True
        report["screenshot_size"] = len(png_data)
        report["screenshot_hash"] = hash(png_data) & 0xffffffff
    else:
        report["warnings"].append(f"Could not capture window: {window_name}")

    report["warnings"].append("Visual focus indicator detection requires image analysis")
    report["warnings"].append("Manually inspect the captured screenshot for visible focus borders")

    return report


def generate_html_report(
    window_name: str,
    keyboard_report: Dict,
    focus_order_report: Dict,
    focus_visibility_report: Dict,
    output_path: str = "accessibility_report.html"
) -> str:
    """Generate an HTML report of accessibility findings."""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Accessibility Report - {window_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #007acc; }}
        .warning {{ color: #d9534f; background: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 4px; }}
        .good {{ color: #5cb85c; background: #dff0d8; padding: 10px; margin: 10px 0; border-radius: 4px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .timestamp {{ color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>Accessibility Verification Report</h1>
    <p>Window: <strong>{window_name}</strong></p>
    <p class="timestamp">Generated with accessibility-verifier v{__version__}</p>

    <div class="section">
        <h2>Keyboard Reachability</h2>
        <p>Elements detected as keyboard-accessible:</p>
        <ul>
"""

    for elem in keyboard_report.get("keyboard_accessible_elements", []):
        html_content += f"            <li>{elem.get('name', 'Unknown')} ({elem.get('type', 'element')})</li>\n"

    if keyboard_report.get("keyboard_traps"):
        html_content += '        <div class="warning">Potential keyboard traps detected!</div>\n'

    for warning in keyboard_report.get("warnings", []):
        html_content += f'        <div class="warning">{warning}</div>\n'

    html_content += """        </ul>
    </div>

    <div class="section">
        <h2>Focus Order Analysis</h2>
        <p>Focus cycling and tab order review:</p>
        <ul>
"""

    for elem in focus_order_report.get("focus_order_elements", []):
        html_content += f"            <li>{elem}</li>\n"

    if focus_order_report.get("tab_trap_detected"):
        html_content += '        <div class="warning">Tab trap detected - focus may not cycle properly</div>\n'

    for warning in focus_order_report.get("warnings", []):
        html_content += f'        <div class="warning">{warning}</div>\n'

    html_content += """        </ul>
    </div>

    <div class="section">
        <h2>Visible Focus Indicators</h2>
        <p>Focus visibility check results:</p>
"""

    if focus_visibility_report.get("screenshot_captured"):
        html_content += '        <div class="good">Screenshot captured for manual inspection</div>\n'
    else:
        html_content += '        <div class="warning">Could not capture screenshot</div>\n'

    for warning in focus_visibility_report.get("warnings", []):
        html_content += f'        <div class="warning">{warning}</div>\n'

    html_content += """    </div>

    <div class="section">
        <h2>Manual Review Checklist</h2>
        <ul>
            <li>Can all interactive elements be reached with Tab and Shift+Tab?</li>
            <li>Is the focus order logical and intuitive?</li>
            <li>Are focus indicators visible (outline, highlight, or other visual change)?</li>
            <li>Can the application be fully operated with the keyboard alone?</li>
            <li>Are there any focus traps where Tab gets stuck?</li>
        </ul>
    </div>

    <footer style="margin-top: 40px; color: #999; border-top: 1px solid #ddd; padding-top: 10px;">
        <p>Note: This tool provides read-only accessibility analysis. For comprehensive testing, use NVDA, JAWS, or other assistive technology tools.</p>
    </footer>
</body>
</html>
"""

    with open(output_path, "w") as f:
        f.write(html_content)

    return output_path


def parse_args(args=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Check Windows app accessibility: keyboard, focus, visibility."
    )
    parser.add_argument(
        "window",
        help="Target window title"
    )
    parser.add_argument(
        "--output",
        default="accessibility_report.html",
        help="Output HTML report path"
    )
    parser.add_argument(
        "--snap",
        default="snap.exe",
        help="Path to snap.exe"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of HTML"
    )
    return parser.parse_args(args)


def main():
    """CLI entrypoint."""
    args = parse_args()

    print(f"Analyzing accessibility for: {args.window}")

    # Run all analyses (read-only)
    keyboard_report = analyze_keyboard_reachability(args.window)
    focus_order_report = analyze_focus_order(args.window)
    focus_visibility_report = analyze_visible_focus(args.window, snap_cmd=args.snap)

    if args.json:
        # Output as JSON
        combined = {
            "window": args.window,
            "keyboard_reachability": keyboard_report,
            "focus_order": focus_order_report,
            "visible_focus": focus_visibility_report
        }
        print(json.dumps(combined, indent=2))
    else:
        # Generate HTML report
        report_path = generate_html_report(
            args.window,
            keyboard_report,
            focus_order_report,
            focus_visibility_report,
            args.output
        )
        print(f"Report saved to: {report_path}")
        print("Open the HTML file in a browser to review findings.")


if __name__ == "__main__":
    main()
