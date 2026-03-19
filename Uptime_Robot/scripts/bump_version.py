#!/usr/bin/env python3
"""
Update version in all project files
"""
import re
import sys
from pathlib import Path


def update_version_file(version: str):
    """Update src/__version__.py"""
    version_path = Path("src/__version__.py")
    
    major, minor, patch = version.split(".")
    
    content = f'''__version__ = "{version}"
__version_info__ = ({major}, {minor}, {patch})
'''
    
    version_path.write_text(content)
    print(f"Updated {version_path}")


def update_debian_control(version: str):
    """Update debian/control"""
    control_path = Path("debian/control")
    
    if not control_path.exists():
        print(f"Warning: {control_path} not found")
        return
    
    content = control_path.read_text()
    
    # Update Version field
    content = re.sub(
        r'^Version: .+$',
        f'Version: {version}',
        content,
        flags=re.MULTILINE
    )
    
    control_path.write_text(content)
    print(f"Updated {control_path}")


def update_pyproject_toml(version: str):
    """Update pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    
    if not pyproject_path.exists():
        print(f"Warning: {pyproject_path} not found")
        return
    
    content = pyproject_path.read_text()
    
    # Update version field
    content = re.sub(
        r'^version = "[^"]+"',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    pyproject_path.write_text(content)
    print(f"Updated {pyproject_path}")


def update_dockerfile(version: str):
    """Add version label to Dockerfile"""
    dockerfile_path = Path("Dockerfile")
    
    if not dockerfile_path.exists():
        print(f"Warning: {dockerfile_path} not found")
        return
    
    content = dockerfile_path.read_text()
    
    # Add/update version label
    if "LABEL version=" in content:
        content = re.sub(
            r'LABEL version="[^"]+"',
            f'LABEL version="{version}"',
            content
        )
    else:
        # Add after FROM instruction
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("FROM "):
                lines.insert(i + 1, f'LABEL version="{version}"')
                break
        content = "\n".join(lines)
    
    dockerfile_path.write_text(content)
    print(f"Updated {dockerfile_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <version>")
        print("Example: python bump_version.py 1.2.3")
        sys.exit(1)
    
    version = sys.argv[1]
    
    # Validate version format
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        print(f"Error: Invalid version format: {version}")
        print("Expected format: X.Y.Z (e.g., 1.2.3)")
        sys.exit(1)
    
    print(f"Bumping version to {version}...")
    
    update_version_file(version)
    update_debian_control(version)
    update_pyproject_toml(version)
    update_dockerfile(version)
    
    print(f"\n✓ Version bumped to {version}")


if __name__ == "__main__":
    main()
