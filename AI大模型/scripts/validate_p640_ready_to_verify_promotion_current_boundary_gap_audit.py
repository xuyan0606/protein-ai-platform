#!/usr/bin/env python3
"""Validate the P640 ready-to-verify promotion current boundary gap audit."""

from p493_p497_gap_audit_common import CONFIGS, validate_audit


if __name__ == "__main__":
    raise SystemExit(validate_audit(CONFIGS["p640"]))
