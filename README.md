# AWS Self Serve IAM
Managing AWS environment Self Service Access IAM permissions

## Overview

This system allows teams to manage AWS IAM access through YAML configuration files and Python scripts. It supports:

- **Custom IAM Policies** - Define policies combining AWS managed policies and custom statements
- **Permanent Access** - Grant long-term access to users and roles
- **Temporary Access** - Time-limited access with automatic expiration validation
- **Multi-Account Support** - Manage access across multiple AWS accounts

## Prerequisites

### 1. AWS Credentials

Set up AWS credentials with appropriate permissions:

```bash
# Configure AWS CLI
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### 2. IAM Deployer Role

Create an IAM role named `AWSSelfServeDeployer` in each AWS account you want to manage:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreatePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:ListPolicyVersions",
        "iam:AttachUserPolicy",
        "iam:AttachRolePolicy",
        "iam:DetachUserPolicy",
        "iam:DetachRolePolicy",
        "iam:PutUserPolicy",
        "iam:DeleteUserPolicy",
        "iam:ListUserPolicies"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust Policy** for the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<your-central-account-id>:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 3. Python Dependencies

```bash
cd aws/scripts
pip install -r requirements.txt
```

## Directory Structure

```
aws/
├── aws-accounts/           # AWS account mappings
│   └── example-team.yaml
├── aws-policies/           # Custom policy definitions
│   └── example-team.yaml
├── permanent-access/       # Permanent access grants
│   └── example-team.yaml
├── temporary-access/       # Temporary access grants
│   └── example-team.yaml
└── scripts/
    ├── aws_iam_manager.py  # Core IAM management class
    ├── apply.py            # Apply configurations
    ├── cleanup.py          # Remove expired access
    ├── validate.py         # Validate expiration dates
    └── requirements.txt    # Python dependencies
```

## Configuration Files

### 1. AWS Accounts (`aws-accounts/team.yaml`)

Map environment names to AWS account IDs:

```yaml
aws-accounts:
  nonprod: "123456789012"
  acceptance: "234567890123"
  prod: "345678901234"
```

### 2. AWS Policies (`aws-policies/team.yaml`)

Define custom IAM policies:

```yaml
aws-policies:
  dev.read-only:
    description: "Read Only access for developers"
    managed_policies:
      - "arn:aws:iam::aws:policy/ReadOnlyAccess"
    custom_statements:
      - effect: "Allow"
        actions:
          - "s3:ListBucket"
          - "ec2:DescribeInstances"
        resources: ["*"]

  dev.break-glass:
    description: "Break-glass access with write permissions"
    managed_policies:
      - "arn:aws:iam::aws:policy/PowerUserAccess"
```

### 3. Permanent Access (`permanent-access/team.yaml`)

Grant long-term access:

```yaml
permanent-access:
  - description: Team read-only access to non-prod
    users:
      - user1@example.com
      - user2@example.com
    environments:
      - nonprod
      - acceptance
    grants:
      - dev.read-only

  - description: CI/CD role access
    roles:
      - github-actions-deployer
    environments:
      - nonprod
    grants:
      - dev.break-glass
```

**Note:** User emails are converted to IAM usernames by removing the domain (e.g., `user@example.com` → `user`).

### 4. Temporary Access (`temporary-access/team.yaml`)

Grant time-limited access:

```yaml
temporary-access:
  - description: Debug production database
    expiration_date: 2025-11-30
    user: developer@example.com
    environment: prod
    grant: dev.break-glass
```

**Important:** Expiration dates must not be more than 6 days in the future (configurable).

## Usage

### Validate Configuration

Before applying changes, validate expiration dates:

```bash
cd aws/scripts
python validate.py example-team
```

### Apply Configuration

Deploy IAM configuration for a team:

```bash
# Apply changes
python apply.py example-team

# Dry run (preview changes without applying)
python apply.py example-team --dry-run
```

This will:
1. Create/update custom IAM policies in all accounts
2. Attach policies to users and roles for permanent access
3. Grant temporary access with time-based conditions

### Cleanup Expired Access

Remove expired temporary access grants:

```bash
# Remove expired access
python cleanup.py example-team

# Dry run
python cleanup.py example-team --dry-run
```

**Recommendation:** Run this daily via cron or GitHub Actions to automatically clean up expired access.

## How It Works

### Custom Policies

The system creates customer-managed IAM policies in each AWS account with names like `team-policy-name`. These policies combine:
- AWS managed policies (attached separately)
- Custom IAM statements (bundled into a single policy)

### Permanent Access

Attaches both managed and custom policies to IAM users or roles using `AttachUserPolicy`/`AttachRolePolicy`.

### Temporary Access

Creates **inline user policies** with time-based IAM conditions:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["..."],
    "Resource": "*",
    "Condition": {
      "DateLessThan": {
        "aws:CurrentTime": "2025-11-30T23:59:59Z"
      }
    }
  }]
}
```

After the expiration date, AWS automatically denies access. The cleanup script removes the inline policy.

### Cross-Account Access

The system uses AWS STS `AssumeRole` to manage IAM in multiple accounts. Each target account must have the `IAMAsCodeDeployer` role with appropriate trust relationships.

## GitHub Actions Integration

Create a workflow to automatically apply changes:

```yaml
name: Apply AWS IAM

on:
  push:
    branches: [main]
    paths:
      - 'aws/**'

jobs:
  apply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/GitHubActionsRole
          aws-region: us-east-1

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd /scripts
          pip install -r requirements.txt

      - name: Validate
        run: |
          cd /scripts
          python validate.py example-team

      - name: Apply
        run: |
          cd /scripts
          python apply.py example-team
```

## Security Considerations

1. **Least Privilege** - The deployer role should only have IAM permissions, not full admin
2. **Audit Trail** - All IAM changes are logged in AWS CloudTrail
3. **Code Review** - All changes should go through PR review before merging
4. **Temporary Access Limits** - Enforce maximum duration (in this example 6 days is the  default)
5. **Automated Cleanup** - Run cleanup script daily to remove expired access. For example using Lambda or GitHub Actions CRON.
6. **MFA** - Consider requiring MFA for production access
7. **Permission Boundaries** - Use IAM permission boundaries to limit maximum permissions

## Troubleshooting

### Authentication Errors

```
Error assuming role in account: AccessDenied
```

**Solution:** Ensure the IAMAsCodeDeployer role exists in the target account with proper trust policy.

### User Not Found

```
Error attaching policy to user@example.com: NoSuchEntity
```

**Solution:** IAM users must already exist. The system converts emails to usernames (removes domain). Create the user first for example with the CLI:

```bash
aws iam create-user --user-name username
```

### Policy Version Limit

```
Error creating policy version: LimitExceeded
```

**Solution:** AWS limits policies to 5 versions. The script automatically deletes old versions, but if this fails, manually delete old versions:

```bash
aws iam list-policy-versions --policy-arn <arn>
aws iam delete-policy-version --policy-arn <arn> --version-id v1
```

## Local Testing

Test with a sandbox AWS account:

```bash
# Use specific AWS profile
export AWS_PROFILE=sandbox

# Dry run first
python apply.py example-team --dry-run

# Apply changes
python apply.py example-team
```

## Next Steps

1. Create your team's configuration files in the respective directories
2. Validate the configuration
3. Run a dry-run to preview changes
4. Apply the configuration
5. Set up automated cleanup via cron or GitHub Actions

## Support

For questions or issues, refer to the main project documentation or create an issue in the repository.
