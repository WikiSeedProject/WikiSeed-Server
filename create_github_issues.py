#!/usr/bin/env python3
"""
GitHub Issues Bulk Creator for WikiSeed Documentation Review

This script creates GitHub issues in bulk from the issues_data.json file.
It uses the GitHub REST API to create issues with proper labels and formatting.

Usage:
    export GITHUB_TOKEN="your_github_token_here"
    python create_github_issues.py [--dry-run] [--repo OWNER/REPO]

Requirements:
    pip install requests
"""

import json
import os
import sys
import time
import argparse
from typing import Dict, List
import requests


class GitHubIssueCreator:
    """Creates GitHub issues via REST API"""

    def __init__(self, token: str, repo: str, dry_run: bool = False):
        """
        Initialize the issue creator

        Args:
            token: GitHub personal access token with repo scope
            repo: Repository in format "owner/repo"
            dry_run: If True, don't actually create issues
        """
        self.token = token
        self.repo = repo
        self.dry_run = dry_run
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }

    def create_issue(self, title: str, body: str, labels: List[str]) -> Dict:
        """
        Create a single GitHub issue

        Args:
            title: Issue title
            body: Issue body (markdown)
            labels: List of label names

        Returns:
            API response as dict
        """
        url = f"{self.api_base}/repos/{self.repo}/issues"

        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }

        if self.dry_run:
            print(f"\n{'='*80}")
            print(f"[DRY RUN] Would create issue:")
            print(f"Title: {title}")
            print(f"Labels: {', '.join(labels)}")
            print(f"Body preview: {body[:200]}...")
            print(f"{'='*80}\n")
            return {"number": "DRY_RUN", "html_url": "dry_run"}

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Error creating issue '{title}': {e}")
            print(f"Response: {response.text}")
            raise

    def ensure_labels_exist(self, labels: List[str]) -> None:
        """
        Ensure all required labels exist in the repository

        Args:
            labels: List of unique label names
        """
        if self.dry_run:
            print(f"[DRY RUN] Would ensure these labels exist: {', '.join(labels)}")
            return

        url = f"{self.api_base}/repos/{self.repo}/labels"

        # Get existing labels
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            existing_labels = {label["name"] for label in response.json()}
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching labels: {e}")
            return

        # Label colors for different categories
        label_colors = {
            "documentation": "0075ca",
            "architecture": "d93f0b",
            "bug": "d73a4a",
            "needs-decision": "fbca04",
            "database": "1d76db",
            "blocker": "b60205",
            "operations": "5319e7",
            "disaster-recovery": "e99695",
            "performance": "d4c5f9",
            "dependencies": "0366d6",
            "security": "ee0701",
            "configuration": "c5def5",
            "devops": "bfd4f2",
            "quality": "c2e0c6",
            "testing": "a2eeef",
            "enhancement": "a2eeef",
            "distribution": "7057ff",
            "monitoring": "e4e669",
            "storage": "fbca04",
            "clarification-needed": "d876e3",
            "job-queue": "1d76db",
            "concurrency": "d4c5f9",
            "frontend": "0e8a16",
            "typo": "fef2c0",
            "formatting": "fef2c0",
            "consistency": "bfd4f2",
            "error-handling": "d93f0b",
            "visualization": "bfdadc",
            "question": "d876e3",
            "torrents": "5319e7",
            "edge-case": "fbca04",
            "downloads": "1d76db",
            "future-proofing": "0e8a16",
            "preservation": "0052cc",
            "reliability": "0052cc",
            "auto-discovery": "c2e0c6",
            "metrics": "e4e669",
            "goals": "0075ca",
            "ux": "a2eeef",
            "risk": "d93f0b",
            "docker": "bfd4f2",
            "git": "bfd4f2"
        }

        # Create missing labels
        for label in labels:
            if label not in existing_labels:
                color = label_colors.get(label, "ededed")  # Default gray
                payload = {
                    "name": label,
                    "color": color,
                    "description": ""
                }
                try:
                    response = requests.post(url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    print(f"✓ Created label: {label}")
                except requests.exceptions.HTTPError as e:
                    print(f"✗ Failed to create label '{label}': {e}")

    def create_issues_from_file(self, filename: str) -> None:
        """
        Create issues from JSON data file

        Args:
            filename: Path to issues_data.json
        """
        # Load issues data
        with open(filename, 'r') as f:
            data = json.load(f)

        issues = data.get("issues", [])

        if not issues:
            print("No issues found in data file")
            return

        print(f"Found {len(issues)} issues to create")

        # Collect all unique labels
        all_labels = set()
        for issue in issues:
            all_labels.update(issue.get("labels", []))

        # Ensure labels exist
        print(f"\nEnsuring {len(all_labels)} labels exist...")
        self.ensure_labels_exist(sorted(all_labels))

        # Create issues
        print(f"\n{'='*80}")
        print("Creating issues...")
        print(f"{'='*80}\n")

        created_issues = []
        failed_issues = []

        for idx, issue_data in enumerate(issues, 1):
            title = issue_data.get("title", "")
            body = issue_data.get("body", "")
            labels = issue_data.get("labels", [])
            priority = issue_data.get("priority", "")

            # Add priority to body if specified
            if priority:
                body = f"**Priority: {priority.capitalize()}**\n\n{body}"

            print(f"[{idx}/{len(issues)}] Creating: {title}")

            try:
                result = self.create_issue(title, body, labels)
                created_issues.append(result)

                if not self.dry_run:
                    print(f"  ✓ Created: {result['html_url']}")
                    # Rate limiting: GitHub allows 5000 requests/hour
                    # Sleep 1 second between requests to be safe
                    time.sleep(1)

            except Exception as e:
                print(f"  ✗ Failed: {e}")
                failed_issues.append({"title": title, "error": str(e)})

        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Total issues: {len(issues)}")
        print(f"Successfully created: {len(created_issues)}")
        print(f"Failed: {len(failed_issues)}")

        if failed_issues:
            print("\nFailed issues:")
            for fail in failed_issues:
                print(f"  - {fail['title']}: {fail['error']}")

        if not self.dry_run and created_issues:
            print(f"\n✓ All issues created successfully!")
            print(f"View them at: https://github.com/{self.repo}/issues")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk create GitHub issues from issues_data.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview issues without creating them"
    )
    parser.add_argument(
        "--repo",
        default="WikiSeedProject/WikiSeed",
        help="Repository in format owner/repo (default: WikiSeedProject/WikiSeed)"
    )
    parser.add_argument(
        "--file",
        default="issues_data.json",
        help="Path to issues data file (default: issues_data.json)"
    )

    args = parser.parse_args()

    # Get GitHub token from environment
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("\nTo get a token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Click 'Generate new token (classic)'")
        print("3. Select 'repo' scope")
        print("4. Copy the token and run:")
        print("   export GITHUB_TOKEN='your_token_here'")
        sys.exit(1)

    # Check if data file exists
    if not os.path.exists(args.file):
        print(f"Error: Data file '{args.file}' not found")
        sys.exit(1)

    # Create issues
    creator = GitHubIssueCreator(token, args.repo, args.dry_run)

    try:
        creator.create_issues_from_file(args.file)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
