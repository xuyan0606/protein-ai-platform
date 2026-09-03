#!/usr/bin/env python3
"""Build P652 P0 external-input closeout readiness gate shell."""

from p648_p652_p0_response_shell_common import CONFIGS, build_layer


if __name__ == "__main__":
    raise SystemExit(build_layer(CONFIGS["p652"]))
