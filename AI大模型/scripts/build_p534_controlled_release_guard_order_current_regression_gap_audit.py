#!/usr/bin/env python3
"""Build the P534 controlled release-guard order current regression gap audit."""

from p493_p497_gap_audit_common import CONFIGS, build_audit


if __name__ == "__main__":
    raise SystemExit(build_audit(CONFIGS["p534"]))
