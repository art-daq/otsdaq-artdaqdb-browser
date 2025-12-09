"""
File: __main__.py
Purpose: Entry point for OTS Browser application.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: main
Complexity: Low | Lines: 163
"""

import argparse
import atexit
import sys
from pathlib import Path
from .app import OTSBrowserApp
from .lockfile import check_and_acquire_lock, cleanup_lock

try:
    from .cache import CacheManager

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    CacheManager = None


def main():
    parser = argparse.ArgumentParser(description="OTS Configuration Browser - Browse OTS configuration data")
    parser.add_argument(
        "data_source",
        nargs="?",
        default="./sampledata/teststand_db",
        help="Path to data directory or MongoDB connection string",
    )
    parser.add_argument(
        "--mongodb", action="store_const", const="mongodb", dest="backend_type", help="Force MongoDB backend"
    )
    parser.add_argument(
        "--directory",
        "--filesystem",
        action="store_const",
        const="filesystem",
        dest="backend_type",
        help="Force filesystem backend",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--cache-dir", type=Path, help="Custom cache directory (default: ~/.ots-browser/cache/)")
    parser.add_argument("--purge-cache", action="store_true", help="Purge cache and exit")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache and exit")
    parser.add_argument("--show-dates", action="store_true", help="Show creation and assignment dates in tables")
    parser.add_argument("--no-lock", action="store_true", help="Disable lock file check (allow multiple instances)")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force start by killing any existing instance without prompting"
    )
    parser.add_argument("--version", action="version", version="OTS Browser 1.0.0")
    args = parser.parse_args()
    if args.purge_cache or args.clear_cache:
        if not CACHE_AVAILABLE:
            print("Error: Cache system is not available (missing sqlite3 support)")
            return 1
        cache_dir = args.cache_dir or CacheManager.DEFAULT_CACHE_DIR
        cache = CacheManager(cache_dir=cache_dir)
        if args.purge_cache:
            print("Purging expired cache entries...")
            cache.purge()
            stats = cache.get_stats()
            print(f"Cache purged. Remaining entries: {stats.get('size', 0)}")
        if args.clear_cache:
            print("Clearing all cache...")
            cache.clear()
            print("Cache cleared.")
        cache.close()
        return 0
    if not args.no_lock:
        if not check_and_acquire_lock(force=args.force):
            return 1
        atexit.register(cleanup_lock)
    try:
        app = OTSBrowserApp(
            data_source=args.data_source,
            backend_type=args.backend_type,
            cache_enabled=not args.no_cache,
            cache_dir=args.cache_dir,
        )
        if args.show_dates:
            app.state.view.show_dates = True
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if not args.no_lock:
            cleanup_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
