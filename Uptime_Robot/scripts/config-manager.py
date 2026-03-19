#!/usr/bin/env python3
"""
Configuration Manager for Uptime Monitor
Handles logging and backup of configuration changes
"""

import os
import sys
import json
import shutil
from datetime import datetime

# Configuration paths
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/etc/uptime-monitor/config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = '/etc/uptime-monitor/config.json'

def load_config():
    """Load configuration from file"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_backup_dir():
    """Get backup directory from config or use default"""
    config = load_config()
    return config.get('backup', {}).get('backup_dir', '/etc/uptime-monitor/config.backups')

def get_log_dir():
    """Get log directory from config or use default"""
    config = load_config()
    return config.get('log_dir', '/var/log/uptime-monitor')

def create_backup():
    """Create a backup of current configuration"""
    try:
        if not os.path.exists(CONFIG_PATH):
            print(f"Error: Config file not found at {CONFIG_PATH}")
            return False
        
        backup_dir = get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_file = os.path.join(backup_dir, f'config.{timestamp}.json')
        
        shutil.copy2(CONFIG_PATH, backup_file)
        
        # Update symlinks
        latest_link = os.path.join(backup_dir, 'config.latest.json')
        prev_link = os.path.join(backup_dir, 'config.previous.json')
        
        if os.path.islink(latest_link) or os.path.exists(latest_link):
            if os.path.islink(prev_link) or os.path.exists(prev_link):
                os.remove(prev_link)
            if os.path.islink(latest_link):
                os.symlink(os.readlink(latest_link), prev_link)
            os.remove(latest_link)
        
        os.symlink(backup_file, latest_link)
        
        # Clean old backups
        config = load_config()
        max_backups = config.get('backup', {}).get('max_backups', 10)
        backups = sorted([f for f in os.listdir(backup_dir) 
                         if f.startswith('config.') and f.endswith('.json') 
                         and not f.endswith('.latest.json') 
                         and not f.endswith('.previous.json')])
        
        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                os.remove(os.path.join(backup_dir, old_backup))
        
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def log_change(old_config, new_config, user='system'):
    """Log configuration changes"""
    try:
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'config-changes.log')
        
        # Find differences
        changes = {}
        for key in set(old_config.keys()) | set(new_config.keys()):
            if old_config.get(key) != new_config.get(key):
                changes[key] = {
                    'old': old_config.get(key),
                    'new': new_config.get(key)
                }
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user': user,
            'action': 'config_changed',
            'changes': changes
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        return True
    except Exception as e:
        print(f"Error logging change: {e}")
        return False

def trigger_system_backup(comment="Configuration changed"):
    """Trigger system backup after configuration change"""
    try:
        # Get backup destination from config
        config = load_config()
        backup_config = config.get('backup', {})
        
        if not backup_config.get('enabled', True):
            return False
        
        # Check if on-change backups are enabled
        if backup_config.get('on_change_backup', True):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            backup_script = os.path.join(script_dir, 'backup-system.sh')
            
            if os.path.exists(backup_script):
                import subprocess
                # Run backup in background
                subprocess.Popen([
                    'bash', backup_script,
                    '--type', 'on-change',
                    '--dest', backup_config.get('backup_dir', '/backup/uptime-monitor'),
                    '--comment', comment,
                    '--quiet'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except Exception as e:
        print(f"Error triggering backup: {e}")
    
    return False

def list_backups():
    """List all available backups"""
    try:
        backup_dir = get_backup_dir()
        if not os.path.exists(backup_dir):
            print("No backups found.")
            return []
        
        backups = [f for f in os.listdir(backup_dir) 
                  if f.startswith('config.') and f.endswith('.json')
                  and not f.endswith('.latest.json')
                  and not f.endswith('.previous.json')]
        backups.sort(reverse=True)
        
        return backups
    except Exception as e:
        print(f"Error listing backups: {e}")
        return []

def show_diff(backup_file):
    """Show differences between current config and backup"""
    try:
        backup_dir = get_backup_dir()
        backup_path = os.path.join(backup_dir, backup_file)
        
        if not os.path.exists(backup_path):
            print(f"Backup not found: {backup_file}")
            return False
        
        with open(backup_path, 'r') as f:
            backup_config = json.load(f)
        
        current_config = load_config()
        
        print(f"\nDifferences from {backup_file}:")
        print("=" * 60)
        
        for key in set(current_config.keys()) | set(backup_config.keys()):
            if current_config.get(key) != backup_config.get(key):
                print(f"\n{key}:")
                print(f"  Backup:  {backup_config.get(key)}")
                print(f"  Current: {current_config.get(key)}")
        
        return True
    except Exception as e:
        print(f"Error showing diff: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: config-manager.py <command> [options]")
        print("")
        print("Commands:")
        print("  backup              Create a backup of current configuration")
        print("  list                List all available backups")
        print("  diff <backup>       Show differences from a backup")
        print("  log <old> <new>     Log a configuration change")
        print("")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        if create_backup():
            print("Backup created successfully.")
        else:
            print("Failed to create backup.")
            sys.exit(1)
    
    elif command == 'list':
        backups = list_backups()
        if backups:
            print("\nAvailable backups:")
            print("=" * 60)
            for i, backup in enumerate(backups, 1):
                print(f"{i}. {backup}")
            print("")
            print("Latest:  config.latest.json ->", os.readlink(os.path.join(get_backup_dir(), 'config.latest.json')) if os.path.islink(os.path.join(get_backup_dir(), 'config.latest.json')) else 'N/A')
            print("Previous: config.previous.json ->", os.readlink(os.path.join(get_backup_dir(), 'config.previous.json')) if os.path.islink(os.path.join(get_backup_dir(), 'config.previous.json')) else 'N/A')
        else:
            print("No backups available.")
    
    elif command == 'diff':
        if len(sys.argv) < 3:
            print("Usage: config-manager.py diff <backup_file>")
            sys.exit(1)
        show_diff(sys.argv[2])
    
    elif command == 'log':
        if len(sys.argv) < 4:
            print("Usage: config-manager.py log <old_config_file> <new_config_file>")
            sys.exit(1)
        
        with open(sys.argv[2], 'r') as f:
            old_config = json.load(f)
        with open(sys.argv[3], 'r') as f:
            new_config = json.load(f)
        
        user = os.environ.get('USER', 'system')
        if log_change(old_config, new_config, user):
            print("Change logged successfully.")
        else:
            print("Failed to log change.")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main()
