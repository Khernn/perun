from __future__ import annotations

import os
import threading

function_metrics = []
function_metrics_out = {}
threading_lock = threading.Lock()
call_stacks = {}
thread_stacks = {}
thread_parents = {}
first_event_for_thread = {}


def event_start_or_resume(event_key, current_time, call_stack):
    call_info = {
        'start_time': current_time,
        'trace': list(call_stack),
        'nested_calls_time': 0,
        'exclusive_time': 0,
        'inclusive_time': 0,
        'exceptions': [],
    }

    with threading_lock:
        call_stack.append((event_key, call_info))
        if event_key not in function_metrics_out:
            function_metrics_out[event_key] = []
        function_metrics_out[event_key].append(call_info)


def event_return_or_yield(current_time, call_stack):
    if call_stack:
        _, call_info = call_stack.pop()
        update_call_info(call_info, current_time, call_stack)


def event_exception(current_time, call_stack, exception):
    if call_stack:
        _, call_info = call_stack.pop()
        update_call_info(call_info, current_time, call_stack)
        call_info['exceptions'].append(exception)


def update_call_info(call_info, current_time, call_stack):
    total_duration = current_time - call_info['start_time']
    exclusive_duration = total_duration - call_info['nested_calls_time']
    call_info['exclusive_time'] = exclusive_duration
    call_info['inclusive_time'] = total_duration
    if call_stack:
        call_stack[-1][1]['nested_calls_time'] += total_duration
        call_stack[-1][1]['inclusive_time'] += total_duration


def get_call_stack(thread_id):
    if thread_id not in call_stacks:
        parent_thread_id = thread_parents.get(thread_id, None)
        if parent_thread_id in call_stacks:
            call_stacks[thread_id] = call_stacks[parent_thread_id].copy()
        else:
            call_stacks[thread_id] = []
    return call_stacks[thread_id]


def process_data():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.cache'), 'r') as file:
        for line in file.readlines():
            parts = line.strip().split(',')
            event_tuple = (parts[0], parts[1], float(parts[2]), parts[3])
            function_metrics.append(event_tuple)

    for event in function_metrics:
        event_type = event[0]
        event_key = event[1]
        time = event[2]
        event_exception_var = event[3]

        event_key_parts = event_key.split(":")
        thread_id = event_key_parts[-1]

        if thread_id not in first_event_for_thread and (event_type == 'PY_START' or event_type == 'PY_RESUME'):
            first_event_for_thread[thread_id] = event

            if not thread_parents:
                thread_parents[thread_id] = None
            else:
                for prev_event in function_metrics[:function_metrics.index(event)]:
                    if thread_id not in prev_event:
                        parent_thread_id = prev_event[1].rsplit(":", 1)[-1]
                        thread_parents[thread_id] = parent_thread_id
                        break

        if thread_id not in thread_stacks:
            thread_stacks[thread_id] = []
            thread_stacks[thread_id].append(event_key)
        call_stack = get_call_stack(thread_id)
        thread_stacks[thread_id].append(call_stack.copy())
        if event_type in ['PY_START', 'PY_RESUME']:
            event_start_or_resume(event_key, time, call_stack)
        elif event_type in ['PY_RETURN', 'PY_YIELD']:
            for event_key_start in thread_stacks[thread_id]:
                if event_key_start == event_key:
                    del thread_stacks[thread_id]
            event_return_or_yield(time, call_stack)
        elif event_type in ['PY_THROW', 'PY_UNWIND']:
            for event_key_start in thread_stacks[thread_id]:
                if event_key_start == event_key:
                    del thread_stacks[thread_id]
            event_exception(time, call_stack, event_exception_var)


def get_trace(call_stack):
    trace = []
    for item in call_stack:
        if item is not None:
            parts = item.split(':')
            trace_info = {
                "source": parts[0],
                "function": parts[1],
                "line": int(parts[2]),
            }
            trace.append(trace_info)
    return trace


def parse_events():
    process_data()

    resources = []
    for key, calls in function_metrics_out.items():
        for call in calls:
            parts = key.split(':')
            uid = {
                "source": parts[0],
                "function": parts[1],
                "line": int(parts[2]),
            }
            resources.append(
                {
                    "amount": float(call['exclusive_time']),
                    "uid": uid,
                    "tid": parts[-1],
                    "type": "time",
                    "trace": get_trace([f"{t[0]}" for t in call['trace']]),
                    "exceptions": call['exceptions'],
                }
            )
    return resources
