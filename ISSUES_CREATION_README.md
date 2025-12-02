# GitHub Issues Bulk Creation Guide

This guide explains how to bulk-create all 49 issues from the documentation review using the provided Python script.

## Prerequisites

1. **Python 3.7+** installed
2. **requests library** installed: `pip install requests`
3. **GitHub Personal Access Token** with `repo` scope

## Getting a GitHub Token

1. Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Give it a name like "WikiSeed Issue Creator"
4. Select the **`repo`** scope (full control of private repositories)
5. Click **"Generate token"**
6. **Copy the token immediately** (you won't see it again!)

## Usage

### Step 1: Set Your GitHub Token

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### Step 2: Preview Issues (Dry Run)

Test the script without creating actual issues:

```bash
python create_github_issues.py --dry-run
```

This will show you what issues would be created without actually creating them.

### Step 3: Create Issues

Once you're satisfied with the preview, create the issues:

```bash
python create_github_issues.py
```

The script will:
- ✅ Create all missing labels with appropriate colors
- ✅ Create all 49 issues in order
- ✅ Apply proper labels to each issue
- ✅ Include priority levels in issue bodies
- ✅ Rate-limit requests (1 second between issues)
- ✅ Display progress and results

### Step 4: Verify

After completion, visit:
```
https://github.com/WikiSeedProject/WikiSeed/issues
```

## Options

```bash
# Use a different repository
python create_github_issues.py --repo "owner/repo"

# Use a different data file
python create_github_issues.py --file "custom_issues.json"

# Dry run with custom repo
python create_github_issues.py --dry-run --repo "owner/repo"

# Show help
python create_github_issues.py --help
```

## What Gets Created

### Issues by Priority

- 🔴 **Critical**: 8 issues (blocker labels)
- 🟡 **Moderate**: 12 issues
- 🟢 **Minor**: 10 issues (typos, formatting)
- ❓ **Questions**: 19 issues (clarifications needed)

**Total: 49 issues**

### Labels Created

The script automatically creates these labels if they don't exist:

**Priority/Status:**
- `blocker` - Red
- `needs-decision` - Yellow
- `enhancement` - Blue

**Category:**
- `documentation` - Blue
- `architecture` - Orange
- `database` - Dark blue
- `security` - Red
- `performance` - Purple
- `operations` - Purple
- `testing` - Light blue
- `devops` - Light blue
- `frontend` - Green
- `bug` - Red

**Type:**
- `question` - Purple
- `typo` - Light yellow
- `clarification-needed` - Purple

And many more categorization labels...

## Troubleshooting

### Error: "GITHUB_TOKEN environment variable not set"

**Solution:** Export your token first:
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### Error: "401 Unauthorized"

**Causes:**
- Token is invalid or expired
- Token doesn't have `repo` scope

**Solution:** Generate a new token with proper permissions

### Error: "403 Forbidden"

**Causes:**
- Rate limit exceeded (unlikely with 1s delays)
- Token doesn't have access to the repository

**Solution:**
- Wait a few minutes and retry
- Verify you have write access to the repository

### Error: "422 Unprocessable Entity"

**Causes:**
- Issue with data format
- Label name too long
- Duplicate issue

**Solution:** Check the error message for details

### Script Interrupted

If you interrupt the script (Ctrl+C), simply run it again. The script will:
- Skip labels that already exist
- Not create duplicate issues (you'll need to manually skip already-created ones)

## Rate Limits

GitHub API allows:
- **5000 requests/hour** for authenticated requests
- Script creates ~50 issues with 1 second delay = **~1 minute total**
- Well within rate limits ✓

## Manual Alternative

If you prefer not to use the script, you can manually create issues using the `ISSUES.md` file:

1. Open `ISSUES.md`
2. Copy each issue's content
3. Go to https://github.com/WikiSeedProject/WikiSeed/issues/new
4. Paste title and description
5. Add labels
6. Submit

**Estimated time:** ~2 hours for all 49 issues

## Files

- `create_github_issues.py` - Main script
- `issues_data.json` - Structured issue data (49 issues)
- `ISSUES.md` - Human-readable issue list
- `ISSUES_CREATION_README.md` - This file

## Security Notes

⚠️ **Never commit your GitHub token to git!**

The script reads the token from environment variables only. If you accidentally commit a token:
1. Immediately revoke it at https://github.com/settings/tokens
2. Generate a new one
3. Remove it from git history

## Support

If you encounter issues:
1. Check the error message carefully
2. Verify your token has correct permissions
3. Try the `--dry-run` flag to debug
4. Check GitHub's status at https://www.githubstatus.com/

## Next Steps

After creating the issues:

1. **Triage Critical Issues** (#1-8)
   - Start with database schema (#3)
   - Define version requirements (#7)
   - Document secrets management (#8)

2. **Label Issues**
   - Add milestone: "Phase 1 - Foundation"
   - Assign issues to team members
   - Set up project board

3. **Create Project Board**
   - Create columns: To Do, In Progress, Review, Done
   - Add all issues to board
   - Prioritize by label

4. **Start Fixing**
   - Begin with quick wins (typos)
   - Move to critical blockers
   - Answer questions as team discusses

---

**Generated for WikiSeed Documentation Review**
**Date:** 2025-12-02
**Total Issues:** 49
