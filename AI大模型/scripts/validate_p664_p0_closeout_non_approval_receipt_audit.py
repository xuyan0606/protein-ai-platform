#!/usr/bin/env python3
"""Validate P664 P0 closeout non-approval receipt audit."""

from p648_p652_p0_response_shell_common import CONFIGS, validate_layer


if __name__ == "__main__":
    raise SystemExit(validate_layer(CONFIGS["p664"]))
