#!/usr/bin/env python3
"""Build P674 P0 terminal blocked-state rollup audit."""

from p648_p652_p0_response_shell_common import CONFIGS, build_layer


if __name__ == "__main__":
    raise SystemExit(build_layer(CONFIGS["p674"]))
