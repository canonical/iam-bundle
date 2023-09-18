#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


import argparse
import re
import sys
from functools import singledispatch
from io import TextIOWrapper
from pathlib import Path
from textwrap import dedent
from typing import MutableMapping

from git import Repo
from jinja2 import Environment, FileSystemLoader

CHANNELS = re.compile(r"^(latest/|[0-9].[0-9]/)?(edge|beta|candidate|stable)$")
ROOT_DIR = Repo(Path(__file__), search_parent_directories=True).working_dir
TEMPLATE_DIRS = [ROOT_DIR, Path(ROOT_DIR) / "templates"]


def channel_type(arg_value):
    if not CHANNELS.match(arg_value):
        raise argparse.ArgumentTypeError("invalid channel")
    return arg_value


@singledispatch
def generate_output(output, content: str) -> None:
    raise NotImplementedError


@generate_output.register(str)
@generate_output.register(Path)
def _(output, content: str) -> None:
    with open(output, mode="wt", encoding="utf-8") as dest:
        dest.write(content)


@generate_output.register
def _(output: TextIOWrapper, content: str) -> None:
    with output:
        output.write(content)


def process_template_variables(variables: str) -> dict[str, str]:
    vars_ = (var.split("=") for var in variables.split(","))
    return {key: val for key, val in vars_}


def render_bundle_file(template_file: Path, variables: MutableMapping[str, str]) -> str:
    template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIRS))
    template = template_env.get_template(template_file.name)
    return template.render(**variables)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """
            Utility to render Identity Platform juju bundle file.

            Examples:

            # Render to a file
            python bundle_renderer.py bundle.yaml.j2 -o <output file> -c <channel> --variables <key1>=<value1>,<key2>=<value2>

            # Render to console
            python bundle_renderer.py bundle.yaml.j2 -c <channel> --variables <key>=<value>
        """
        ),
    )

    parser.add_argument(
        "template",
        type=Path,
        help="the Jinja template of the bundle file",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        type=Path,
        help="the rendered bundle file",
    )
    parser.add_argument(
        "-c",
        "--channel",
        dest="channel",
        required=True,
        type=channel_type,
        help="the CharmHub channel to publish the bundle",
    )
    parser.add_argument(
        "--variables",
        type=process_template_variables,
        default={},
        help=(
            """
            the variables provided to render the bundle file
            (e.g. <key1>=<value1>,<key2>=<value2>)
        """
        ),
    )
    args = parser.parse_args()

    variables = {**args.variables, **{"channel": args.channel}}
    rendered_content = render_bundle_file(args.template, variables)

    dest = (
        args.output_file
        if args.output_file
        else TextIOWrapper(sys.stdout.buffer, encoding=sys.stdout.encoding)
    )
    generate_output(dest, rendered_content)


if __name__ == "__main__":
    main()
