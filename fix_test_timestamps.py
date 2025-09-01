#!/usr/bin/env python3
"""
Script to fix timestamp and room ID set issues in test files.
"""

import os
import re


def fix_test_file(filepath):
    """Fix timestamp and room ID set issues in a test file."""
    print(f"Processing {filepath}...")

    with open(filepath, "r") as f:
        content = f.read()

    original_content = content

    # Pattern 1: Fix start_time assignments that are in seconds (need to be milliseconds)
    # Look for start_time = small numbers (likely seconds) and convert to milliseconds
    content = re.sub(
        r"(bot\.start_time = )(\d{10})(?!\d)",  # 10-digit numbers (seconds)
        r"\g<1>\g<2>000  # Converted to milliseconds",
        content,
    )

    # Pattern 2: Fix start_time assignments that are already correct but missing comments
    content = re.sub(
        r"(bot\.start_time = )(\d{13})(?!\d)(?!.*# )",  # 13-digit numbers without comments
        r"\g<1>\g<2>  # Milliseconds",
        content,
    )

    # Pattern 3: Fix server_timestamp assignments that are in seconds
    content = re.sub(
        r"(\.server_timestamp = )(\d{10})(?!\d)",  # 10-digit numbers (seconds)
        r"\g<1>\g<2>000  # Converted to milliseconds",
        content,
    )

    # Pattern 4: Add room ID set population after BibleBot creation
    # Look for patterns like: bot = BibleBot(config=..., client=...)
    # And add the room ID set population if it's not already there

    # First, find all BibleBot instantiations
    bot_creation_pattern = r"(\s+)(bot = BibleBot\(config=([^,]+), client=([^)]+)\))\n"

    def add_room_id_set(match):
        indent = match.group(1)
        bot_creation = match.group(2)
        config_var = match.group(3)

        # Check if room ID set is already populated in the next few lines
        # This is a simple heuristic - we'll look ahead a bit
        return f'{indent}{bot_creation}\n{indent}# Populate room ID set for testing (normally done in initialize())\n{indent}bot._room_id_set = set({config_var}["matrix_room_ids"])\n'

    # Apply the room ID set fix
    content = re.sub(bot_creation_pattern, add_room_id_set, content)

    # Also handle bot_instance cases
    bot_instance_pattern = r"(\s+)(bot_instance = bot\.BibleBot\(([^)]+)\))\n"

    def add_room_id_set_instance(match):
        indent = match.group(1)
        bot_creation = match.group(2)
        config_var = match.group(3)

        return f'{indent}{bot_creation}\n{indent}# Populate room ID set for testing (normally done in initialize())\n{indent}bot_instance._room_id_set = set({config_var}["matrix_room_ids"])\n'

    content = re.sub(bot_instance_pattern, add_room_id_set_instance, content)

    # Remove duplicate room ID set assignments
    content = re.sub(
        r"(\s+# Populate room ID set for testing.*\n\s+bot\._room_id_set = set.*\n)(\s+# Populate room ID set for testing.*\n\s+bot\._room_id_set = set.*\n)",
        r"\g<1>",
        content,
    )

    if content != original_content:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  ✓ Fixed {filepath}")
        return True
    else:
        print(f"  - No changes needed for {filepath}")
        return False


def main():
    """Main function to fix all test files."""
    test_files = [
        "tests/test_edge_cases.py",
        "tests/test_integration_patterns.py",
        "tests/test_monitoring_patterns.py",
        "tests/test_performance_patterns.py",
        "tests/test_reliability_patterns.py",
        "tests/test_scalability_patterns.py",
        "tests/test_security_patterns.py",
    ]

    fixed_count = 0
    for filepath in test_files:
        if os.path.exists(filepath):
            if fix_test_file(filepath):
                fixed_count += 1
        else:
            print(f"Warning: {filepath} not found")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
