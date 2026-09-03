#!/usr/bin/env python3
"""Validate the P497 stage25 operator docs sync receipt gap audit."""

from p493_p497_gap_audit_common import CONFIGS, validate_audit


if __name__ == "__main__":
    raise SystemExit(validate_audit(CONFIGS["p497"]))
