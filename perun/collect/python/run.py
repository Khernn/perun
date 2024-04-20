from typing import Any
import subprocess
import os
import shutil
import time

import click

from perun.collect.python import parser
from perun.logic import runner
from perun.utils import log
from perun.utils.structs import Executable, CollectStatus


def before(**kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Checking for Dependencies")
    try:
        shutil.which('python3.12')
        log.minor_success("Checking dependencies")
        return CollectStatus.OK, "", dict(kwargs)
    except Exception:
        log.minor_fail("Checking dependencies")
        return CollectStatus.ERROR, "Python 3.12 is required for the 'python' collector.", dict(kwargs)


def collect(executable: Executable, **kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Collecting events")
    try:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(current_dir, 'collect.py')
        args = [executable.cmd]
        if kwargs['filter']:
            args.append(';'.join(map(str, kwargs['filter'])))
        start_time = time.perf_counter()
        result = subprocess.run(['python3.12', script_path] + args, capture_output=True, text=True, check=True)
        print(result.stdout)
        print(result.stderr)
        log.minor_success("Collecting events")
        log.major_info(f'Finished in {round(time.perf_counter() - start_time, 5)} seconds.')
        return CollectStatus.OK, "", dict(kwargs)
    except Exception as e:
        return CollectStatus.ERROR, f"{e}\nThe collect script failed to start", dict(kwargs)


def after(**kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    log.major_info("Parse events")
    start_time = time.perf_counter()
    parsed_events = parser.ParseEvents()
    resources = parsed_events.get_resources()
    kwargs["profile"] = {
        "global": {
            "resources": resources,
        }
    }
    log.minor_success("Parse events")
    log.major_info(f'Finished in {round(time.perf_counter() - start_time, 5)} seconds.')
    return CollectStatus.OK, "", dict(kwargs)


# def teardown():
#     pass


@click.command()
@click.option(
    '--filter',
    '-f',
    multiple=True,
    help='Filters to apply e.g.: -f "contextlib.py" -f "/usr/lib/python3.12" -f "/Library/Frameworks/".'
)
@click.pass_context
# TODO: Consider adding an option to specify the path for Python 3.12.
def python(ctx: click.Context, **kwargs: Any) -> None:
    runner.run_collector_from_cli_context(ctx, "python", kwargs)
