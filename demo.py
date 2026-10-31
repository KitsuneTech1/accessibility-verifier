"""
Demo for accessibility-verifier.
Shows how to check a window for keyboard accessibility and focus indicators.
"""

import json
import accessibility_verifier as av


def main():
    print("accessibility-verifier demo")
    print()

    window_name = "Notepad"
    print(f"Checking accessibility for: {window_name}")
    print()

    # Run analyses
    keyboard_report = av.analyze_keyboard_reachability(window_name)
    focus_order_report = av.analyze_focus_order(window_name)
    focus_visibility_report = av.analyze_visible_focus(window_name)

    # Combine results
    combined = {
        "window": window_name,
        "keyboard_reachability": keyboard_report,
        "focus_order": focus_order_report,
        "visible_focus": focus_visibility_report
    }

    print("Analysis Results (JSON):")
    print(json.dumps(combined, indent=2))
    print()

    # Generate HTML report
    report_path = av.generate_html_report(
        window_name,
        keyboard_report,
        focus_order_report,
        focus_visibility_report,
        "accessibility_report.html"
    )

    print(f"HTML report saved to: {report_path}")
    print("Open it in a browser for detailed findings.")


if __name__ == "__main__":
    main()
