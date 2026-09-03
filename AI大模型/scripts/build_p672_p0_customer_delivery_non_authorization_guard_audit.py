#!/usr/bin/env python3
"""Build P672 P0 customer delivery non-authorization guard audit."""

from p648_p652_p0_response_shell_common import CONFIGS, build_layer


if __name__ == "__main__":
    raise SystemExit(build_layer(CONFIGS["p672"]))
