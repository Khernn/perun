from __future__ import annotations

import os
import threading

function_metrics = []
function_metrics_out = {}
threading_lock = threading.Lock()
call_stacks = {}


def event_start_or_resume(event_key, current_time, call_stack):
    call_info = {
        'start_time': current_time,
        'trace': list(call_stack),
        'nested_calls_time': 0,
        'exclusive_time': 0,
        'inclusive_time': 0,
        'exceptions': [],
    }

    call_stack.append((event_key, call_info))
    with threading_lock:
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
        call_stacks[thread_id] = []
    return call_stacks[thread_id]


def process_data():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.cache'), 'r') as file:
        for line in file.readlines():
            parts = line.strip().split(',')
            event_tuple = (parts[0], parts[1], float(parts[2]))
            function_metrics.append(event_tuple)
    for event in function_metrics:
        event_type = event[0]
        event_key = event[1]
        time = event[2]

        event_key_parts = event_key.split(":")
        thread_id = event_key_parts[-1]

        call_stack = get_call_stack(thread_id)
        if event_type in ['PY_START', 'PY_RESUME']:
            event_start_or_resume(event_key, time, call_stack)
        elif event_type in ['PY_RETURN', 'PY_YIELD']:
            event_return_or_yield(time, call_stack)
        elif event_type in ['PY_THROW', 'PY_UNWIND']:
            event_exception(time, call_stack, Exception)


def append_trace_item(simplified_trace, item, count):
    if count > 1:
        simplified_trace.append(f"... {item} (x{count})")
    elif item is not None:
        simplified_trace.append(item)


def simplify_trace(trace):
    simplified_trace = []
    last_seen, repeat_count = None, 1

    for item in trace:
        if item == last_seen:
            repeat_count += 1
        else:
            if last_seen is not None:
                append_trace_item(simplified_trace, last_seen, repeat_count)
            last_seen, repeat_count = item, 1

    append_trace_item(simplified_trace, last_seen, repeat_count)
    return simplified_trace


def parse_events():
    print('Parsing events')
    process_data()
    # print("Function Path:Function Name:TID | Call Count | Total Exclusive Time | Total Inclusive Time | Exceptions Count | Trace\n")
    # for key, calls in function_metrics_out.items():
    #     for call in calls:
    #         trace = simplify_trace([f"{t[0]}" for t in call['trace']])
    #         trace_str = " -> ".join(trace)
    #         print(f"{key} | {len(calls)} | {call['exclusive_time']:.6f} | {call['inclusive_time']:.6f} | {len(call['exceptions'])} | {trace_str}\n")

    resources = []
    for key in function_metrics_out.keys():
        resources.append(
            {
                "amount": int(1),
                "uid": key,
            }
        )
    return resources
