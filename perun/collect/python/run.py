from typing import Any
import subprocess
import os

import click

from perun.collect.python import parser
from perun.logic import runner
from perun.utils import log
from perun.utils.structs import CollectStatus


def before(**kwargs):
    log.major_info("Checking for Dependencies")
    try:
        subprocess.run(['python3.12', '--version'], capture_output=True, text=True, check=True)
        log.minor_success("Checking dependencies")
        return CollectStatus.OK, "", dict(kwargs)
    except Exception:
        log.minor_fail("Checking dependencies")
        return CollectStatus.ERROR, "Python 3.12 is required for the 'python' collector.", dict(kwargs)


def collect(**kwargs):
    try:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(current_dir, 'collect_events.py')
        args = [kwargs['filename']]
        if kwargs['filter']:
            args.append(';'.join(map(str, kwargs['filter'])))
        result = subprocess.run(['python3.12', script_path] + args, capture_output=True, text=True, check=True)
        print(result.stdout)
        print(result.stderr)
        return CollectStatus.OK, "", dict(kwargs)
    except Exception:
        return CollectStatus.ERROR, "The collect script failed to start", dict(kwargs)


def after(**kwargs):
    resources = parser.parse_events()
    kwargs["profile"] = {
        "global": {
            "resources": resources,
        }
    }
    return CollectStatus.OK, "", dict(kwargs)


@click.command()
@click.pass_context
@click.argument(
    'filename',
)
@click.option(
    '--filter',
    '-f',
    multiple=True,
    help='Filters to apply e.g.: -f "frozen codecs","contextlib.py","/usr/lib/python3.12","/Library/Frameworks/".'
)
# TODO: Consider adding an option to specify the path for Python 3.12.
def python(ctx: click.Context, **kwargs: Any) -> None:
    runner.run_collector_from_cli_context(ctx, "python", kwargs)
