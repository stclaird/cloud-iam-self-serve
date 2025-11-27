#!/usr/bin/env python3
"""
Apply IAM configuration for a team
Usage: python apply.py <team-name> [--dry-run]
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aws_iam_manager import AWSIAMManager


def main():
    if len(sys.argv) < 2:
        print("Usage: python apply.py <team-name> [--dry-run]")
        print("\nExample:")
        print("  python apply.py example-team")
        print("  python apply.py example-team --dry-run")
        sys.exit(1)
    
    team = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")
    
    try:
        manager = AWSIAMManager(team, dry_run=dry_run)
        manager.apply_all()
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Configuration file not found")
        print(f"   {e}")
        print(f"\n   Make sure the following files exist:")
        print(f"   - aws-accounts/{team}.yaml")
        print(f"   - aws-policies/{team}.yaml")
        print(f"   - permanent-access/{team}.yaml")
        print(f"   - temporary-access/{team}.yaml")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error applying configuration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
