#!/usr/bin/env python3
"""Validate P670 P0 release claim non-promotion status board."""

from p648_p652_p0_response_shell_common import CONFIGS, validate_layer


if __name__ == "__main__":
    raise SystemExit(validate_layer(CONFIGS["p670"]))
