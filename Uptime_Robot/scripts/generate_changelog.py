#!/usr/bin/env python3
"""
Generate CHANGELOG.md from git commits
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_commits_since_tag(tag: str = None) -> list:
    """Get commits since last tag or all commits"""
    if tag:
        cmd = f"git log {tag}..HEAD --pretty=format:'%s' --no-merges"
    else:
        cmd = "git log --pretty=format:'%s' --no-merges"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return []

    commits = result.stdout.strip().split("\n")
    return [c.strip("'") for c in commits if c]


def categorize_commits(commits: list) -> dict:
    """Categorize commits by type"""
    categories = {
        "added": [],
        "changed": [],
        "fixed": [],
        "removed": [],
        "security": [],
    }

    for commit in commits:
        commit_lower = commit.lower()

        if any(x in commit_lower for x in ["add", "create", "implement", "new"]):
            categories["added"].append(commit)
        elif any(x in commit_lower for x in ["fix", "bug", "patch"]):
            categories["fixed"].append(commit)
        elif any(x in commit_lower for x in ["remove", "delete", "drop"]):
            categories["removed"].append(commit)
        elif any(x in commit_lower for x in ["security", "vulnerability", "cve"]):
            categories["security"].append(commit)
        else:
            categories["changed"].append(commit)

    return categories


def generate_changelog_entry(
    version: str, commits: list, output_file: str = None
) -> str:
    """Generate changelog entry for a version"""
    categories = categorize_commits(commits)

    date = datetime.now().strftime("%Y-%m-%d")

    entry = f"## [{version}] - {date}\n\n"

    if categories["added"]:
        entry += "### Added\n"
        for commit in categories["added"]:
            entry += f"- {commit}\n"
        entry += "\n"

    if categories["changed"]:
        entry += "### Changed\n"
        for commit in categories["changed"]:
            entry += f"- {commit}\n"
        entry += "\n"

    if categories["fixed"]:
        entry += "### Fixed\n"
        for commit in categories["fixed"]:
            entry += f"- {commit}\n"
        entry += "\n"

    if categories["security"]:
        entry += "### Security\n"
        for commit in categories["security"]:
            entry += f"- {commit}\n"
        entry += "\n"

    if categories["removed"]:
        entry += "### Removed\n"
        for commit in categories["removed"]:
            entry += f"- {commit}\n"
        entry += "\n"

    if output_file:
        changelog_path = Path(output_file)

        if changelog_path.exists():
            existing_content = changelog_path.read_text()
            # Insert after header
            if "# Changelog" in existing_content:
                parts = existing_content.split("\n\n", 1)
                if len(parts) > 1:
                    new_content = parts[0] + "\n\n" + entry + parts[1]
                else:
                    new_content = parts[0] + "\n\n" + entry
            else:
                new_content = "# Changelog\n\n" + entry + existing_content
        else:
            new_content = "# Changelog\n\n" + entry

        changelog_path.write_text(new_content)
        print(f"Updated {changelog_path}")

    return entry


def generate_release_notes(version: str, output_file: str = "release_notes.md"):
    """Generate release notes for GitHub Release"""
    # Remove 'v' prefix if present
    version_clean = version.lstrip("v")

    # Get previous tag
    result = subprocess.run(
        "git describe --tags --abbrev=0 HEAD~1 2>/dev/null || echo ''",
        shell=True,
        capture_output=True,
        text=True,
    )
    previous_tag = result.stdout.strip()

    # Get commits since previous tag
    commits = (
        get_commits_since_tag(previous_tag) if previous_tag else get_commits_since_tag()
    )

    if not commits:
        commits = ["Initial release"]

    # Generate release notes
    notes = f"# Release {version}\n\n"
    notes += f"**Release Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
    notes += "## Changes\n\n"

    categories = categorize_commits(commits)

    if categories["added"]:
        notes += "### Added\n"
        for commit in categories["added"]:
            notes += f"- {commit}\n"
        notes += "\n"

    if categories["changed"]:
        notes += "### Changed\n"
        for commit in categories["changed"]:
            notes += f"- {commit}\n"
        notes += "\n"

    if categories["fixed"]:
        notes += "### Fixed\n"
        for commit in categories["fixed"]:
            notes += f"- {commit}\n"
        notes += "\n"

    notes += "## Installation\n\n"
    notes += "### Linux (CURL)\n"
    notes += "```bash\n"
    notes += f"curl -fsSL https://raw.githubusercontent.com/ajjs1ajjs/Uptime-Monitor/main/install.sh | sudo bash\n"
    notes += "```\n\n"

    notes += "### Linux (APT)\n"
    notes += "```bash\n"
    notes += "sudo apt update && sudo apt install uptime-monitor\n"
    notes += "```\n\n"

    notes += "### Docker\n"
    notes += "```bash\n"
    notes += f"docker pull ghcr.io/ajjs1ajjs/uptime-monitor:{version_clean}\n"
    notes += "```\n\n"

    notes += "### Windows\n"
    notes += "Download `uptime-monitor-windows-{version}.zip` from assets below.\n"

    # Write to file
    Path(output_file).write_text(notes)
    print(f"Generated {output_file}")

    return notes


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_changelog.py <version> [--output FILE]")
        print("Example: python generate_changelog.py 1.2.3")
        print("         python generate_changelog.py v1.2.3 --output release_notes.md")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")

    output_file = "CHANGELOG.md"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    # Get previous tag
    result = subprocess.run(
        "git describe --tags --abbrev=0 HEAD~ 2>/dev/null || echo ''",
        shell=True,
        capture_output=True,
        text=True,
    )
    previous_tag = result.stdout.strip()

    # Get commits
    commits = (
        get_commits_since_tag(previous_tag) if previous_tag else get_commits_since_tag()
    )

    if "--release-notes" in sys.argv or output_file == "release_notes.md":
        generate_release_notes(f"v{version}", output_file)
    else:
        generate_changelog_entry(version, commits, output_file)


if __name__ == "__main__":
    main()
