# accessibility-verifier

accessibility-verifier checks Windows applications for keyboard reachability, focus order, and visible focus indicators. It helps identify accessibility barriers for keyboard and assistive technology users.

This tool provides read-only analysis and never sends input to the target window.

## Features

- Check keyboard reachability of UI elements
- Analyze focus order and detect potential focus traps
- Inspect visible focus indicators
- Generate HTML accessibility reports
- Read-only: never modifies the target application
- Works with any Windows application

## Requirements

- Python 3.8 or higher
- Windows operating system
- Optional: pywinauto or comtypes for enhanced UI Automation (currently uses basic detection)
- snap.exe for window capture (focus state visualization)

## Installation

```bash
git clone https://github.com/KitsuneTech1/accessibility-verifier.git
cd accessibility-verifier
```

## CLI Usage

Check a window and generate an HTML report:

```bash
python accessibility_verifier.py "Window Title"
```

Options:

- `--output`: Custom HTML report path (default: accessibility_report.html)
- `--snap`: Path to snap.exe (default: snap.exe)
- `--json`: Output JSON instead of HTML

## Examples

```bash
# Check Notepad for accessibility
python accessibility_verifier.py "Notepad"

# Custom report location
python accessibility_verifier.py "My App" --output "my_app_a11y.html"

# JSON output
python accessibility_verifier.py "My App" --json
```

## Python API

```python
from accessibility_verifier import (
    analyze_keyboard_reachability,
    analyze_focus_order,
    analyze_visible_focus,
    generate_html_report
)

# Check keyboard reachability
keyboard_report = analyze_keyboard_reachability("MyApp")

# Check focus order
focus_order_report = analyze_focus_order("MyApp")

# Check visible focus
focus_visibility_report = analyze_visible_focus("MyApp")

# Generate HTML report
generate_html_report(
    "MyApp",
    keyboard_report,
    focus_order_report,
    focus_visibility_report
)
```

## Manual Verification Checklist

After running the tool, manually verify:

- Can all interactive elements be reached with Tab and Shift+Tab?
- Is the focus order logical and follows visual layout?
- Are focus indicators clearly visible?
- Can the entire application be operated with keyboard alone?
- Are there any focus traps where Tab gets stuck?

## Limitations

This tool provides basic accessibility analysis. For comprehensive testing, use:

- NVDA (free screen reader): https://www.nvaccess.org/
- JAWS (commercial screen reader)
- Axe DevTools
- WAVE Accessibility Checker
- Windows Accessibility Checker (Inspect.exe)

## Running Tests

```bash
python -m unittest discover tests
```

## Running the Demo

```bash
python demo.py
```

## License

MIT License. Copyright (c) 2026 KitsuneTech1.
