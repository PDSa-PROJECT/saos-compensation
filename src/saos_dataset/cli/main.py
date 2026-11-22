"""Search broadly and download complete SAOS judgments without model processing."""

import argparse

from saos_dataset.acquisition.pipeline import run


def parse_arguments(arguments=None):
    """
    Parse explicit CLI overrides without replacing YAML defaults.

    args:
        arguments: Command-line arguments, or None for process arguments.

    returns:
        Namespace containing explicit CLI overrides.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Explicit CLI options override environment, .env and YAML; use process-data for extraction.",
    )
    parser.add_argument(
        "--config-dir",
        help="Acquisition configuration directory (default: configs/dataset/acquisition)",
    )
    parser.add_argument(
        "--search-query",
        default=argparse.SUPPRESS,
        help="Broad SAOS full-text query (default: zadośćuczynienie)",
    )
    parser.add_argument(
        "--max-age-years",
        type=int,
        default=argparse.SUPPRESS,
        help="Judgment date range in years before today",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=argparse.SUPPRESS,
        help="Maximum search pages (100 judgments each); 0 reads all pages",
    )
    parser.add_argument(
        "--max-gib",
        type=float,
        default=argparse.SUPPRESS,
        help="Total output-directory limit in GiB across resumed runs; 0 disables it",
    )
    parser.add_argument(
        "--download-path",
        default=argparse.SUPPRESS,
        help="Raw output directory; absolute or relative to the working directory",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=argparse.SUPPRESS,
        help="HTTP connection/read timeout in seconds, not a total download limit",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=argparse.SUPPRESS,
        help="Print per-page download progress; raw JSON is always saved",
    )
    return parser.parse_args(arguments)


def main():
    """
    Load download settings and run raw acquisition.

    args:
        None

    returns:
        None.
    """
    from saos_dataset.acquisition.settings import load_config

    options = vars(parse_arguments())
    directory = options.pop("config_dir")
    try:
        run(load_config(directory, options))
    except KeyboardInterrupt:
        print(
            "Interrupted. Saved raw pages are preserved; rerun get-raw-data to resume.",
            flush=True,
        )
        raise SystemExit(130)


if __name__ == "__main__":
    main()
