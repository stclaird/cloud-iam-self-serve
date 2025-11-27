#!/usr/bin/env python3
"""
Validate temporary access expiration dates
Ensures expiration dates are not more than 6 days in the future
Usage: python validate.py <team-name>
"""

from ruamel.yaml import YAML
import sys
from datetime import datetime, timedelta, date


def validate_expiration_date(file_path: str):
    """Validate that expiration dates in temporary-access file are within policy limits"""
    yaml = YAML()
    yaml.preserve_quotes = True

    try:
        with open(file_path, 'r') as file:
            data = yaml.load(file)

        if 'temporary-access' not in data:
            print("No 'temporary-access' key found in the YAML.")
            return

        # Use only the date part for now
        now = datetime.now().date()
        six_days_later = now + timedelta(days=6)
        errors_found = False

        for entry in data['temporary-access']:
            if 'expiration_date' not in entry:
                continue

            expiration_date = entry['expiration_date']

            # Ensure expiration_date is a date object
            if not isinstance(expiration_date, date):
                print(f"Invalid expiration_date format: {expiration_date}")
                continue

            if expiration_date > six_days_later:
                errors_found = True
                line, col = entry.lc.key('expiration_date')
                error_str = str(expiration_date)
                print_error_with_context(file_path, line, col, error_str)

        if errors_found:
            print("\n❌ Validation failed. One or more expiration dates are more than 6 days from now.")
            print("   Maximum allowed expiration date: " + str(six_days_later))
            sys.exit(1)
        else:
            print(f"✅ Validation passed. All expiration dates are within policy limits.")
            print(f"   Current date: {now}")
            print(f"   Maximum allowed: {six_days_later}")

    except Exception as e:
        print(f"❌ Error processing the YAML file: {e}")
        sys.exit(1)


def print_error_with_context(file_path: str, error_line: int, error_col: int, 
                            error_str: str, n: int = 3):
    """Print error with surrounding context lines"""
    with open(file_path, 'r') as file:
        lines = file.readlines()

    error_line = error_line + 1

    # Calculate the start and end index for context lines
    start_line = max(error_line - n, 0)
    end_line = min(error_line + n + 1, len(lines))

    # Print context lines with the error line highlighted
    for i in range(start_line, end_line):
        line_prefix = f"{i + 1}: "
        print(f"{line_prefix}{lines[i].rstrip()}")

        if i == error_line - 1:  # After printing the error line, print the indicator
            error_indicator = " " * (error_col + len(str(i + 1)) + 2) + \
                            "^" * len(error_str) + \
                            " - date must not be more than 6 days into the future"
            print(error_indicator)


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <team-name>")
        print("\nExample:")
        print("  python validate.py example-team")
        sys.exit(1)

    team = sys.argv[1]
    file_path = f"../temporary-access/{team}.yaml"
    
    print(f"\n🔍 Validating temporary access for team: {team}")
    print("=" * 60)
    
    validate_expiration_date(file_path)
    
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
