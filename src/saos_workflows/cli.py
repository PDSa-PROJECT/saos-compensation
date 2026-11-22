"""Workflow bootstrap without launching unfinished pipelines."""

import argparse
import json

from .settings import load_collection_config


def main(argv=None):
    """Validate and display the selected future collection configuration.

    args:
        argv: Optional explicit command-line arguments.

    returns:
        Zero after successful validation.
    """
    parser = argparse.ArgumentParser(description="Inspect local SAOS workflow configuration.")
    parser.add_argument("--collection-config", help="Collection YAML (default: configs/workflows/collection.yaml)")
    arguments = parser.parse_args(argv)
    print(json.dumps(load_collection_config(arguments.collection_config), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
