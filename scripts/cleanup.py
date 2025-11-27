#!/usr/bin/env python3
"""
Cleanup expired temporary access grants
Usage: python cleanup.py <team-name> [--dry-run]
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aws_iam_manager import AWSIAMManager


def cleanup_expired_access(team: str, dry_run: bool = False):
    """Remove expired temporary access grants"""
    
    print(f"\n🧹 Cleaning up expired temporary access for team: {team}")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    
    try:
        manager = AWSIAMManager(team, dry_run=dry_run)
        today = datetime.now().date()
        
        expired_count = 0
        active_count = 0
        
        print("\n⏰ Checking temporary access grants...")
        print("-" * 60)
        
        for temp_config in manager.temporary_access:
            expiration = temp_config['expiration_date']
            user = temp_config['user']
            env = temp_config['environment']
            grant = temp_config['grant']
            
            if expiration < today:
                expired_count += 1
                print(f"\n❌ EXPIRED: {temp_config['description']}")
                print(f"   User: {user}")
                print(f"   Environment: {env}")
                print(f"   Grant: {grant}")
                print(f"   Expired: {expiration}")
                
                # Remove the access
                if env in manager.accounts:
                    account_id = manager.accounts[env]
                    manager.remove_temporary_access(account_id, user, grant)
                else:
                    print(f"   ⚠️  Environment '{env}' not found in accounts")
            else:
                active_count += 1
                days_remaining = (expiration - today).days
                print(f"\n✅ ACTIVE: {temp_config['description']}")
                print(f"   User: {user}")
                print(f"   Environment: {env}")
                print(f"   Expires: {expiration} ({days_remaining} days remaining)")
        
        print("\n" + "=" * 60)
        print(f"📊 Summary:")
        print(f"   Expired grants cleaned up: {expired_count}")
        print(f"   Active grants remaining: {active_count}")
        print("=" * 60 + "\n")
        
        return expired_count
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: Configuration file not found")
        print(f"   {e}")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python cleanup.py <team-name> [--dry-run]")
        print("\nExample:")
        print("  python cleanup.py example-team")
        print("  python cleanup.py example-team --dry-run")
        sys.exit(1)
    
    team = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    
    cleanup_expired_access(team, dry_run)


if __name__ == "__main__":
    main()
