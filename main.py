#!/usr/bin/env python3
"""
proxy0 — unified VLESS+Reality proxy manager (multi-provider).

Usage:
  python3 main.py <provider> <command> [args]

Providers:
  vultr   — fully API-managed (create/destroy/rebuild from scratch)
  aliyun  — SWAS; instance is bought in the console, this tool deploys xray onto it

Common commands:
  python3 main.py vultr   create | destroy | rebuild | config | status | check | regions
  python3 main.py aliyun  list | deploy <ip> | config | status | check | destroy | rebuild

Auto-detect (no provider prefix; runs across whichever providers have state):
  python3 main.py status | config | check

Preflight (run this FIRST on a fresh setup — diagnoses missing prerequisites):
  python3 main.py doctor

Adding a new provider:
  1. Create providers/<name>/ with manager.py exposing a COMMANDS dict
  2. Register it in PROVIDERS below
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.vultr import manager as vultr_manager
from providers.aliyun import manager as aliyun_manager

PROVIDERS = {
    "vultr": vultr_manager,
    "v": vultr_manager,
    "aliyun": aliyun_manager,
    "ali": aliyun_manager,
    "a": aliyun_manager,
}

PROVIDER_DISPLAY = {
    vultr_manager: "vultr",
    aliyun_manager: "aliyun",
}


def _all_providers():
    """Distinct provider modules (deduped from aliases)."""
    seen = set()
    out = []
    for m in PROVIDERS.values():
        if id(m) not in seen:
            seen.add(id(m))
            out.append(m)
    return out


def cmd_auto_status():
    any_state = False
    for m in _all_providers():
        from core.connectivity import load_state
        if load_state(m.STATE_FILE):
            any_state = True
            print(f"=== {PROVIDER_DISPLAY[m]} ===")
            m.cmd_status()
            print()
    if not any_state:
        print("No instances configured.")
        print("  Create Vultr : python3 main.py vultr create")
        print("  Deploy Aliyun: python3 main.py aliyun deploy <ip>")


def cmd_auto_config():
    from core.connectivity import load_state
    any_state = False
    for m in _all_providers():
        if load_state(m.STATE_FILE):
            any_state = True
            print(f"=== {PROVIDER_DISPLAY[m]} ===")
            m.cmd_config()
            print()
    if not any_state:
        print("No instances configured")


def cmd_auto_check():
    from core.connectivity import load_state
    any_state = False
    for m in _all_providers():
        if load_state(m.STATE_FILE):
            any_state = True
            print(f"=== {PROVIDER_DISPLAY[m]} ===")
            m.cmd_check()
            print()
    if not any_state:
        print("No instances configured")


def cmd_doctor():
    from core import preflight
    sys.exit(preflight.run())


AUTO_COMMANDS = {
    "status": cmd_auto_status,
    "config": cmd_auto_config,
    "check": cmd_auto_check,
    "doctor": cmd_doctor,
    "preflight": cmd_doctor,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    head = sys.argv[1].lower()

    if head in PROVIDERS:
        manager = PROVIDERS[head]
        if len(sys.argv) < 3:
            print(f"{head} commands: {', '.join(manager.COMMANDS.keys())}")
            sys.exit(1)
        cmd = sys.argv[2].lower()
        if cmd not in manager.COMMANDS:
            print(f"Unknown {head} command: {cmd}")
            print(f"Available: {', '.join(manager.COMMANDS.keys())}")
            sys.exit(1)
        manager.COMMANDS[cmd]()
        return

    if head in AUTO_COMMANDS:
        AUTO_COMMANDS[head]()
        return

    if head in ("-h", "--help", "help"):
        print(__doc__)
        return

    print(f"Unknown provider/command: {head}")
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
