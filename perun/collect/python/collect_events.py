from contextlib import contextmanager
import sys
import time
import threading
import os

function_metrics = []
threading_lock = threading.Lock()
filter_list = [__file__, 'frozen']
event_cache_file = ''
events_to_save = []


def save_events_to_file():
    with open(event_cache_file, 'a') as f:
        for event in events_to_save:
            event_str = f"{event[0]},{event[1]},{event[2]}\n"
            f.write(event_str)
    events_to_save.clear()


def capture_event(event_type, function_code, *args):
    if filter_list and any(ignore in function_code.co_filename for ignore in filter_list):
        return

    thread_id = threading.get_ident()
    event_key = f"{function_code.co_filename}:{function_code.co_name}:{thread_id}"
    current_time = time.perf_counter()

    event = (event_type, event_key, current_time)
    with threading_lock:
        events_to_save.append(event)
        if len(events_to_save) >= 100:
            save_events_to_file()


def register_event_callback(tool_id, event, capture_function):
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
def monitor(tool_id: int):
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
    filename = sys.argv[1]
    try:
        filter_list.extend(sys.argv[2].split(';'))
    except IndexError:
        pass

    event_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.cache')
    with open(event_cache_file, 'w') as f:
        pass

    with open(filename, 'r') as file:
        code = compile(file.read(), filename, 'exec')

    try:
        with monitor(2):
            exec(code, globals(), locals())
        end_time = time.perf_counter()
    except Exception as e:
        print(e)
