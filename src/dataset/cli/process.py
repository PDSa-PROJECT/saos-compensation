"""Extract predictor features and monetary targets from saved raw JSON."""

import argparse
import asyncio


def parse_arguments(arguments=None):
    """Parse processing-only overrides independently of download options.

    args:
        arguments: Explicit argument list, or None for process arguments.

    returns:
        Namespace containing only supplied runtime overrides and config_dir.
    """
    parser = argparse.ArgumentParser(description=__doc__, epilog="Explicit options override processing/process.yaml; model settings remain in YAML.")
    parser.add_argument("--config-dir", help="Processing YAML directory (default: configs/dataset/processing)")
    parser.add_argument("--input-path", default=argparse.SUPPRESS, help="Raw JSON dataset directory; absolute or relative to the project root")
    parser.add_argument("--output-path", default=argparse.SUPPRESS, help="Separate processed-output directory; absolute or relative to the project root")
    parser.add_argument("--max-gib", type=float, default=argparse.SUPPRESS, help="Total processed-output limit in GiB; 0 disables it")
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="HTTP timeout for locality metadata; no SAOS requests")
    parser.add_argument("--debug", action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS, help="Save source/model calls and retain eligible failed target attempts")
    return parser.parse_args(arguments)


def main():
    """Load processing configuration and run local extraction.

    args:
        None.

    returns:
        None.
    """
    from ..extraction.model.configuration import load_config
    from ..processing.pipeline import run

    options = vars(parse_arguments())
    directory = options.pop("config_dir")
    try:
        asyncio.run(run(load_config(directory, options)))
    except KeyboardInterrupt:
        print("Interrupted. Completed model decisions are saved; rerun process-data to resume.", flush=True)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
