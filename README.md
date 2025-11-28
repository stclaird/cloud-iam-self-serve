# IAM Self Serve
Managing Cloud Environment environment access IAM permissions for developers.

## Overview

This system allows teams to manage AWS IAM access through YAML configuration files and Python scripts. It supports:

- **Custom IAM Policies** - Define policies combining AWS managed policies and custom statements
- **Permanent Access** - Grant long-term access to users and roles
- **Temporary Access** - Time-limited access with automatic expiration validation
- **Multi-Account Support** - Manage access across multiple AWS accounts

## What is the purpose of this tool?
Often users need access to a cloud account which is generally managed via IAM roles and polices.  This is often handled via Infrastructure as code by creating users and assigning them to groups or roles often done via Iac tooling such as Terraform. This works well for long term users who need permanent access and have permissions relevant to their job role.  However, sometimes a user needs a different level of permission temporarily, when this happens the cloud administrators have to modify the users perms and ensure that it is taken away when it is no longer required.

This tool allows the users to submit a temporary access permission request which will be automatically expired by IAM once the request's time limit has been reached.

For example, if user Bert needs write access to an S3 bucket for 2 days, Bert would submit a request for access (usually via PR) with the date when you wish the access to expire.  This request would be reviewed by Bert's manager or peers and if the request is valid it would be merged and Bert's access permission would be granted in IAM.  2 days later the permission would expire and Bert would be denied access.

## How might you implement this IAM Self Serve tool?

A good example would to have your own copy (clone or forked) of this repo in your git provider such as github or gitlab. With this in place users can raise permissions requests via pull requests and other users, or perhaps managers can approve this PR.  Then the tool will run on merge and create the permission requests.

## Prerequisites for running the scripts.

### 1. AWS Credentials.
#### For running on your workstation
The tool will need to run as a user or service account that has AWS IAM permissions enough to manage CRUD on IAM users.  These permssions are referred to as an IAM deployer role in this document.
Set up or identify an existing user and

_NOTE_

### 2. IAM Deployer Role

Create an IAM role named `AWSSelfServeDeployer` in each AWS account you want to manage with this tool:

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

### 2. AWS Policies (`aws-policies/your-team.yaml`)

Define custom IAM policies. These are the IAM permissions policies you are going to make available to your users to request when they request a permission.

```yaml
aws-policies:
  developers.read-only:
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
