from contextlib import contextmanager
import sys
import time
import threading
import os
from typing import Any, Callable

function_metrics = []
threading_lock = threading.Lock()
filter_list = [__file__, 'frozen']
event_cache_file = ''
events_to_save = []


def save_events_to_file() -> None:
    """
    Writes accumulated event data to a file and clears the cache.
    """
    with open(event_cache_file, 'a') as f:
        for event in events_to_save:
            event_str = f"{event[0]},{event[1]},{event[2]},{event[3]}\n"
            f.write(event_str)
    events_to_save.clear()


def capture_event(event_type: str, function_code: Any, *args: Any) -> None:
    """
    Captures function execution events, filtering out those from unwanted sources.

    Args:
        event_type (str): Type of the event (e.g., 'PY_THROW', 'PY_UNWIND').
        function_code (Any): Code object of the function where the event occurred.
        *args (Any): Additional arguments related to the event.
    """
    if filter_list and any(ignore in function_code.co_filename or ignore in function_code.co_name for ignore in filter_list):
        return

    thread_id = threading.get_ident()
    function_name = function_code.co_name.replace(' ', '_') if ' ' in function_code.co_name else function_code.co_name
    event_key = f"{function_code.co_filename}:{function_name}:{function_code.co_firstlineno}:{thread_id}"
    current_time = time.perf_counter()

    exception = None
    if event_type in ['PY_THROW', 'PY_UNWIND']:
        try:
            event_exception = args[0] if args else None
            exception = repr(event_exception)
        except Exception:
            exception = "Unknown exception"

    event = (event_type, event_key, current_time, exception)
    with threading_lock:
        events_to_save.append(event)
        if sys.getsizeof(events_to_save) >= 131072:  # 128 KB = 131072 bytes
            save_events_to_file()


def register_event_callback(tool_id: int, event: str, capture_function: Callable[..., None]) -> None:
    """
    Registers a callback for a specific monitoring event type.

    Args:
        tool_id (int): The identifier for the monitoring tool.
        event (str): The event type to monitor.
        capture_function (Callable[..., None]): The function to execute when the event occurs.
    """
    if event in ['PY_START', 'PY_RESUME']:
        sys.monitoring.register_callback(
            tool_id, getattr(sys.monitoring.events, event),
            lambda code, offset: capture_function(event, code)
        )
    elif event in ['PY_RETURN', 'PY_YIELD']:
        sys.monitoring.register_callback(
            tool_id, getattr(sys.monitoring.events, event),
            lambda code, offset, retval: capture_function(event, code, retval)
        )
    elif event in ['PY_THROW', 'PY_UNWIND']:
        sys.monitoring.register_callback(
            tool_id, getattr(sys.monitoring.events, event),
            lambda code, offset, exception: capture_function(event, code, exception)
        )
    else:
        raise ValueError(f'Event handling not implemented for: {event}')


@contextmanager
def monitor(tool_id: int) -> None:
    """
    Context manager for monitoring function executions.

    Args:
        tool_id (int): The identifier for the monitoring tool.
    """
    event_names = ['PY_START', 'PY_RETURN', 'PY_RESUME', 'PY_THROW', 'PY_YIELD', 'PY_UNWIND']

    sys.monitoring.use_tool_id(tool_id, "profile")

    events = (sys.monitoring.events.PY_START
              | sys.monitoring.events.PY_RETURN
              | sys.monitoring.events.PY_RESUME
              | sys.monitoring.events.PY_THROW
              | sys.monitoring.events.PY_YIELD
              | sys.monitoring.events.PY_UNWIND)

    sys.monitoring.set_events(tool_id, events)

    for event in event_names:
        register_event_callback(tool_id, event, capture_event)

    try:
        yield
    finally:
        if events_to_save:
            save_events_to_file()
        sys.monitoring.free_tool_id(tool_id)


if __name__ == "__main__":
    # Retrieve the script filename from command line arguments.
    filename = sys.argv[1]
    try:
        # Extend the filter list with additional file names or identifiers to be ignored during event capture.
        filter_list.extend(sys.argv[2].split(';'))
    except IndexError:
        pass

    event_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.log')
    with open(event_cache_file, 'w') as f:
        pass
    main_dir = os.path.dirname(filename)

    if main_dir not in sys.path:
        sys.path.append(main_dir)

    sys.argv = [filename]
    with open(filename, 'r') as file:
        code = compile(file.read(), filename, 'exec')

    try:
        # Use the monitor context manager to track events during code execution.
        with monitor(2):
            exec(code)
    except Exception as e:
        print(e)
