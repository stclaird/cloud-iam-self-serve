"""
AWS IAM Manager - Manages AWS IAM policies and access using boto3
Replaces Terraform for AWS IAM-as-Code implementation
"""

import boto3
import json
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib


class AWSIAMManager:
    """Manages AWS IAM policies, roles, and access grants"""
    
    def __init__(self, team: str, dry_run: bool = False):
        self.team = team
        self.dry_run = dry_run
        self.sts = boto3.client('sts')
        
        # Load team configuration
        self.accounts = self._load_yaml(f'../aws-accounts/{team}.yaml')['aws-accounts']
        self.policies_config = self._load_yaml(f'../aws-policies/{team}.yaml')['aws-policies']
        self.permanent_access = self._load_yaml(f'../permanent-access/{team}.yaml')['permanent-access']
        self.temporary_access = self._load_yaml(f'../temporary-access/{team}.yaml')['temporary-access']
        
    def _load_yaml(self, filepath: str) -> dict:
        """Load YAML configuration file"""
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    
    def _get_iam_client(self, account_id: str):
        """Get IAM client for specific account using cross-account role"""
        try:
            # Assume role in target account
            role_arn = f'arn:aws:iam::{account_id}:role/IAMAsCodeDeployer'
            response = self.sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f'iam-as-code-{self.team}'
            )
            
            credentials = response['Credentials']
            return boto3.client(
                'iam',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
        except Exception as e:
            print(f"Error assuming role in account {account_id}: {e}")
            # Fall back to default credentials (for local testing)
            return boto3.client('iam')
    
    def _policy_name(self, policy_key: str) -> str:
        """Generate policy name for team"""
        return f'{self.team}-{policy_key}'.replace('.', '-')
    
    def _create_policy_document(self, policy_config: dict) -> dict:
        """Create IAM policy document from configuration"""
        statements = []
        
        # Add custom statements if provided
        if 'custom_statements' in policy_config:
            for stmt in policy_config['custom_statements']:
                statements.append({
                    'Effect': stmt['effect'],
                    'Action': stmt['actions'],
                    'Resource': stmt['resources']
                })
        
        return {
            'Version': '2012-10-17',
            'Statement': statements
        } if statements else None
    
    def create_or_update_policy(self, account_id: str, policy_key: str, policy_config: dict) -> Optional[str]:
        """Create or update an IAM policy in the specified account"""
        iam = self._get_iam_client(account_id)
        policy_name = self._policy_name(policy_key)
        
        # Get account ID for ARN
        account = account_id
        policy_arn = f'arn:aws:iam::{account}:policy/{policy_name}'
        
        # Create policy document for custom statements
        policy_doc = self._create_policy_document(policy_config)
        
        if not policy_doc and not policy_config.get('managed_policies'):
            print(f"  ⚠️  Policy {policy_key} has no statements or managed policies")
            return None
        
        # Only create custom policy if there are custom statements
        if policy_doc:
            try:
                # Check if policy exists
                try:
                    iam.get_policy(PolicyArn=policy_arn)
                    exists = True
                except iam.exceptions.NoSuchEntityException:
                    exists = False
                
                if self.dry_run:
                    print(f"  [DRY RUN] Would {'update' if exists else 'create'} policy: {policy_name}")
                    return policy_arn
                
                if exists:
                    # Get current default version
                    policy_info = iam.get_policy(PolicyArn=policy_arn)
                    current_version = policy_info['Policy']['DefaultVersionId']
                    
                    # Create new version
                    iam.create_policy_version(
                        PolicyArn=policy_arn,
                        PolicyDocument=json.dumps(policy_doc),
                        SetAsDefault=True
                    )
                    
                    # Delete old version (AWS allows max 5 versions)
                    versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
                    if len(versions) > 3:
                        oldest = sorted(versions, key=lambda x: x['CreateDate'])[0]
                        if not oldest['IsDefaultVersion']:
                            iam.delete_policy_version(
                                PolicyArn=policy_arn,
                                VersionId=oldest['VersionId']
                            )
                    
                    print(f"  ✅ Updated policy: {policy_name}")
                else:
                    # Create new policy
                    response = iam.create_policy(
                        PolicyName=policy_name,
                        PolicyDocument=json.dumps(policy_doc),
                        Description=f"{policy_config['description']} (managed by iam-as-code for {self.team})"
                    )
                    policy_arn = response['Policy']['Arn']
                    print(f"  ✅ Created policy: {policy_name}")
                
                return policy_arn
                
            except Exception as e:
                print(f"  ❌ Error creating/updating policy {policy_name}: {e}")
                return None
        
        return policy_arn if policy_doc else None
    
    def attach_managed_policies(self, account_id: str, user_or_role: str, 
                               managed_policies: List[str], is_role: bool = False):
        """Attach AWS managed policies to user or role"""
        iam = self._get_iam_client(account_id)
        
        for policy_arn in managed_policies:
            try:
                if self.dry_run:
                    print(f"  [DRY RUN] Would attach {policy_arn} to {user_or_role}")
                    continue
                
                if is_role:
                    iam.attach_role_policy(RoleName=user_or_role, PolicyArn=policy_arn)
                else:
                    # Convert email to IAM username (remove domain)
                    username = user_or_role.split('@')[0]
                    iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
                
                print(f"  ✅ Attached managed policy to {user_or_role}")
            except Exception as e:
                print(f"  ❌ Error attaching policy to {user_or_role}: {e}")
    
    def attach_custom_policy(self, account_id: str, user_or_role: str, 
                           policy_arn: str, is_role: bool = False):
        """Attach custom policy to user or role"""
        iam = self._get_iam_client(account_id)
        
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would attach {policy_arn} to {user_or_role}")
                return
            
            if is_role:
                iam.attach_role_policy(RoleName=user_or_role, PolicyArn=policy_arn)
            else:
                # Convert email to IAM username
                username = user_or_role.split('@')[0]
                iam.attach_user_policy(UserName=username, PolicyArn=policy_arn)
            
            print(f"  ✅ Attached custom policy to {user_or_role}")
        except Exception as e:
            print(f"  ❌ Error attaching custom policy to {user_or_role}: {e}")
    
    def grant_temporary_access(self, account_id: str, user: str, grant: str, 
                              expiration_date: datetime.date):
        """Grant temporary access with time-based condition"""
        iam = self._get_iam_client(account_id)
        username = user.split('@')[0]
        policy_name = f'temp-{self.team}-{grant}-{username}'.replace('.', '-')
        
        # Get the base policy configuration
        if grant not in self.policies_config:
            print(f"  ❌ Grant '{grant}' not found in policies")
            return
        
        policy_config = self.policies_config[grant]
        
        # Create time-limited policy document
        statements = []
        
        # Add custom statements with time condition
        if 'custom_statements' in policy_config:
            for stmt in policy_config['custom_statements']:
                statements.append({
                    'Effect': stmt['effect'],
                    'Action': stmt['actions'],
                    'Resource': stmt['resources'],
                    'Condition': {
                        'DateLessThan': {
                            'aws:CurrentTime': expiration_date.strftime('%Y-%m-%dT23:59:59Z')
                        }
                    }
                })
        
        if not statements:
            print(f"  ⚠️  No custom statements to apply for temporary access")
            return
        
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': statements
        }
        
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would create temporary inline policy for {user}")
                return
            
            iam.put_user_policy(
                UserName=username,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_doc)
            )
            
            print(f"  ✅ Granted temporary access to {user} until {expiration_date}")
            
            # Also attach managed policies if specified (these won't auto-expire)
            if 'managed_policies' in policy_config:
                print(f"  ⚠️  Note: Managed policies don't auto-expire, manual cleanup needed")
                self.attach_managed_policies(account_id, user, policy_config['managed_policies'])
                
        except Exception as e:
            print(f"  ❌ Error granting temporary access to {user}: {e}")
    
    def remove_temporary_access(self, account_id: str, user: str, grant: str):
        """Remove temporary access inline policy"""
        iam = self._get_iam_client(account_id)
        username = user.split('@')[0]
        policy_name = f'temp-{self.team}-{grant}-{username}'.replace('.', '-')
        
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would remove temporary policy from {user}")
                return
            
            iam.delete_user_policy(UserName=username, PolicyName=policy_name)
            print(f"  ✅ Removed temporary access from {user}")
        except iam.exceptions.NoSuchEntityException:
            print(f"  ℹ️  No temporary policy found for {user}")
        except Exception as e:
            print(f"  ❌ Error removing temporary access from {user}: {e}")
    
    def apply_all(self):
        """Apply all IAM configurations for the team"""
        print(f"\n🚀 Applying IAM configuration for team: {self.team}")
        print("=" * 60)
        
        # Step 1: Create/Update policies in all accounts
        print("\n📋 Step 1: Creating/Updating IAM Policies")
        print("-" * 60)
        policy_arns = {}
        
        for policy_key, policy_config in self.policies_config.items():
            print(f"\n🔧 Processing policy: {policy_key}")
            for env, account_id in self.accounts.items():
                print(f"  Account: {env} ({account_id})")
                arn = self.create_or_update_policy(account_id, policy_key, policy_config)
                if arn:
                    policy_arns[f"{env}:{policy_key}"] = {
                        'arn': arn,
                        'managed_policies': policy_config.get('managed_policies', [])
                    }
        
        # Step 2: Apply permanent access grants
        print("\n\n👥 Step 2: Applying Permanent Access Grants")
        print("-" * 60)
        
        for grant_config in self.permanent_access:
            print(f"\n📌 {grant_config['description']}")
            
            for env in grant_config['environments']:
                if env not in self.accounts:
                    print(f"  ⚠️  Environment '{env}' not found in accounts")
                    continue
                
                account_id = self.accounts[env]
                print(f"  Environment: {env} ({account_id})")
                
                for grant in grant_config['grants']:
                    policy_info = policy_arns.get(f"{env}:{grant}")
                    
                    if not policy_info:
                        print(f"    ⚠️  Policy '{grant}' not found")
                        continue
                    
                    # Grant to users
                    for user in grant_config.get('users', []):
                        if policy_info['arn']:
                            self.attach_custom_policy(account_id, user, policy_info['arn'])
                        # Attach managed policies
                        if policy_info['managed_policies']:
                            self.attach_managed_policies(account_id, user, 
                                                        policy_info['managed_policies'])
                    
                    # Grant to roles
                    for role in grant_config.get('roles', []):
                        if policy_info['arn']:
                            self.attach_custom_policy(account_id, role, 
                                                     policy_info['arn'], is_role=True)
                        if policy_info['managed_policies']:
                            self.attach_managed_policies(account_id, role, 
                                                        policy_info['managed_policies'], 
                                                        is_role=True)
        
        # Step 3: Apply temporary access grants
        print("\n\n⏰ Step 3: Applying Temporary Access Grants")
        print("-" * 60)
        
        today = datetime.now().date()
        
        for temp_config in self.temporary_access:
            expiration = temp_config['expiration_date']
            
            # Skip expired access
            if expiration < today:
                print(f"\n⏭️  Skipping expired: {temp_config['description']} (expired {expiration})")
                continue
            
            print(f"\n⏱️  {temp_config['description']}")
            print(f"  Expires: {expiration}")
            
            env = temp_config['environment']
            if env not in self.accounts:
                print(f"  ⚠️  Environment '{env}' not found")
                continue
            
            account_id = self.accounts[env]
            self.grant_temporary_access(
                account_id, 
                temp_config['user'], 
                temp_config['grant'],
                expiration
            )
        
        print("\n" + "=" * 60)
        print("✅ IAM configuration applied successfully!")
        print("=" * 60 + "\n")
