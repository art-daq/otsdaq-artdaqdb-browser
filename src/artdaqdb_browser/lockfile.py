"""
File: lockfile.py
Purpose: Application lock file to prevent multiple instances.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: get_lock_info, is_process_running, create_lock_file, remove_lock_file, kill_process_gracefully, ...
Complexity: Medium | Lines: 214
"""

import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

LOCK_FILE = Path("/tmp/ots-browser.lock")


def get_lock_info() -> Optional[Tuple[int, float]]:
    if not LOCK_FILE.exists():
        return None
    try:
        content = LOCK_FILE.read_text().strip()
        lines = content.split("\n")
        pid = int(lines[0])
        timestamp = float(lines[1]) if len(lines) > 1 else 0
        return (pid, timestamp)
    except (ValueError, IOError, IndexError):
        return None


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def create_lock_file() -> bool:
    try:
        content = f"{os.getpid()}\n{time.time()}"
        LOCK_FILE.write_text(content)
        return True
    except IOError as e:
        print(f"Warning: Could not create lock file: {e}", file=sys.stderr)
        return False


def remove_lock_file() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except IOError:
        pass


def kill_process_gracefully(pid: int) -> bool:
    if not is_process_running(pid):
        print(f"Process {pid} is not running.")
        return True
    stages = [
        ("Sending SIGTERM (polite termination request)...", signal.SIGTERM),
        ("Process still running. Sending SIGTERM again...", signal.SIGTERM),
        ("Process still running. Sending SIGKILL (force kill)...", signal.SIGKILL),
    ]
    for i, (message, sig) in enumerate(stages):
        print(message)
        try:
            os.kill(pid, sig)
        except OSError as e:
            print(f"  Error sending signal: {e}")
            if not is_process_running(pid):
                print(f"  Process {pid} has terminated.")
                return True
            return False
        if i < len(stages) - 1:
            for _ in range(20):
                time.sleep(0.1)
                if not is_process_running(pid):
                    print(f"  Process {pid} has terminated.")
                    return True
    time.sleep(0.5)
    if is_process_running(pid):
        print(f"  Warning: Process {pid} may still be running (zombie or kernel state)")
        return False
    print(f"  Process {pid} has been terminated.")
    return True


def prompt_kill_existing(pid: int) -> bool:
    print(f"\nAnother instance of OTS Browser is already running (PID: {pid}).")
    print("\nOptions:")
    print("  [y] Yes - Kill the existing instance and start a new one")
    print("  [n] No  - Abort and keep the existing instance running")
    print()
    while True:
        try:
            response = input("Do you want to terminate the existing instance? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return False
        if response in ("", "n", "no"):
            return False
        elif response in ("y", "yes"):
            return True
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def check_and_acquire_lock(force: bool = False) -> bool:
    lock_info = get_lock_info()
    if lock_info:
        (pid, timestamp) = lock_info
        if is_process_running(pid):
            if force:
                print(f"Force mode: Terminating existing instance (PID: {pid})...")
            else:
                if not prompt_kill_existing(pid):
                    print("Aborting. The existing instance will continue running.")
                    return False
                print()
            if not kill_process_gracefully(pid):
                print("Failed to terminate the existing instance. Aborting.")
                return False
            remove_lock_file()
            print()
        else:
            print(f"Found stale lock file (PID {pid} no longer running). Cleaning up...")
            remove_lock_file()
    if not create_lock_file():
        print("Warning: Could not create lock file. Proceeding anyway...")
    return True


def cleanup_lock() -> None:
    lock_info = get_lock_info()
    if lock_info and lock_info[0] == os.getpid():
        remove_lock_file()
