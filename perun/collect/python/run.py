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
    """
    Check for the required dependencies before collection starts.

    :returns tuple: (return code, status message, updated kwargs)
    """
    log.major_info("Checking for Dependencies")
    try:
        shutil.which('python3.12')
        log.minor_success("Checking dependencies")
        return CollectStatus.OK, "", dict(kwargs)
    except Exception:
        log.minor_fail("Checking dependencies")
        return CollectStatus.ERROR, "Python 3.12 is required for the 'python' collector.", dict(kwargs)


def collect(executable: Executable, **kwargs) -> tuple[CollectStatus, str, dict[str, Any]]:
    """
    Collects profiling data by executing a 'collect.py' script.

    :param Executable executable: executable profiled command
    :returns tuple: (return code, status message, updated kwargs)
    """
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
    """
    Parses events after collection and prepares the final profile.

    :param dict kwargs: profile's header
    :return tuple: (return code, status message, updated kwargs)
    """
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
    event_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.log')

    try:
        os.remove(event_cache_file)
    except Exception as e:
        print(f"Error: {event_cache_file} : {e}")

    log.major_info(f'Finished in {round(time.perf_counter() - start_time, 5)} seconds.')
    return CollectStatus.OK, "", dict(kwargs)


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
    """
    Generates `time` performance profile, capturing overall running times of
    user defined and libraries python functions.

    \b
      * **Metric**: running `time`
      * **Dependencies**: `none`
      * **Default units**: `s`

    This is a wrapper over the ``time`` linux utility and captures resources
    in the following form:

    .. code-block:: json

        \b
        {
          "amount": 4.608009476214647e-06,
          "uid": {
            "source": "~/main.py",
            "function": "fibonacci",
            "line": 2
          },
          "tid": "139821382942720",
          "type": "time",
          "ncalls": 1,
          "trace": [
            {
              "source": "~/main.py",
              "function": "<module>",
              "line": 1
            }
          ],
          "exceptions": [
            "ZeroDivisionError('division by zero')"
          ]
        }
    """
    runner.run_collector_from_cli_context(ctx, "python", kwargs)
