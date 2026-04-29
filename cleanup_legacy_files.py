#!/usr/bin/env python3
"""
Legacy File Cleanup Script
Removes outdated files and folders from the dormitory management system.
Run this script from the project root directory.
"""

import os
import shutil
from pathlib import Path

def cleanup_legacy_files():
    """Remove legacy and unused files from the project."""
    
    # Define files and folders to remove
    items_to_remove = [
        # Legacy template folders
        'templates/Landlord',
        'templates/Tenant',
        'templates/archive',
        
        # Development scripts (keep for reference but not needed in production)
        'init_db.py',
        'debug_login.py',
        'scripts/reset_password.py',
        
        # Old database backup (if exists)
        'database/manager - Copy.sql',
    ]
    
    print("=" * 60)
    print("ACCOMMO - Legacy File Cleanup")
    print("=" * 60)
    print()
    
    removed_count = 0
    skipped_count = 0
    
    for item in items_to_remove:
        item_path = Path(item)
        
        if item_path.exists():
            try:
                if item_path.is_dir():
                    shutil.rmtree(item_path)
                    print(f"✓ Removed directory: {item}")
                    removed_count += 1
                else:
                    item_path.unlink()
                    print(f"✓ Removed file: {item}")
                    removed_count += 1
            except Exception as e:
                print(f"✗ Error removing {item}: {e}")
                skipped_count += 1
        else:
            print(f"⊘ Not found: {item}")
            skipped_count += 1
    
    print()
    print("=" * 60)
    print(f"Cleanup Summary:")
    print(f"  Removed: {removed_count} items")
    print(f"  Skipped: {skipped_count} items")
    print("=" * 60)
    print()
    
    # Create backup info file
    create_backup_info()
    
    print("✓ Cleanup complete!")
    print()
    print("Next steps:")
    print("1. Replace old templates with new modern versions")
    print("2. Update _head.html, _nav.html, _footer.html")
    print("3. Test all pages for proper rendering")
    print("4. Verify responsive design on mobile devices")
    print()

def create_backup_info():
    """Create a file documenting removed items."""
    backup_info = """# Legacy Files Removed

This file documents what was removed during the UI/UX modernization.

## Removed Folders
- templates/Landlord/ (5 files) - Old design prototypes
- templates/Tenant/ (2 files) - Legacy tenant pages
- templates/archive/ (2 files) - Archived templates

## Removed Scripts
- init_db.py - Database initialization (replaced by db.py)
- debug_login.py - Debug tool (development only)
- scripts/reset_password.py - Admin tool (not needed in production)

## Removed Database Files
- database/manager - Copy.sql - Backup copy

## Reason for Removal
All removed files were either:
1. Old design prototypes superseded by the new modern UI
2. Development/debug tools not needed in production
3. Duplicate or backup files

## Restoration
If you need to restore any removed files, check your version control history:
```bash
git log --all --full-history -- "path/to/file"
git checkout <commit-hash> -- "path/to/file"
```

## Date Removed
December 2, 2025

## Version
UI/UX Modernization v3.0
"""
    
    with open('REMOVED_FILES.md', 'w') as f:
        f.write(backup_info)
    
    print("✓ Created REMOVED_FILES.md documentation")

def verify_required_files():
    """Verify that required files for the new system exist."""
    required_files = [
        'templates/_base.html',
        'templates/index.html',
        'templates/logIn.html',
        'templates/register.html',
        'app.py',
        'db.py',
        'requirements.txt',
    ]
    
    print()
    print("Verifying required files...")
    print("-" * 60)
    
    all_present = True
    for file in required_files:
        if Path(file).exists():
            print(f"✓ {file}")
        else:
            print(f"✗ Missing: {file}")
            all_present = False
    
    print("-" * 60)
    
    if all_present:
        print("✓ All required files present")
    else:
        print("⚠ Some required files are missing - create them before running the app")
    
    print()

if __name__ == '__main__':
    print()
    response = input("This will delete legacy files. Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        cleanup_legacy_files()
        verify_required_files()
    else:
        print("Cleanup cancelled.")
        print()