from __future__ import annotations
import os

from perun.utils import log


class ParseEvents:
    def __init__(self):
        self.function_metrics_out = {}
        self.call_stacks = {}
        self.thread_stacks = {}
        self.thread_parents = {}
        self.first_event_for_thread = {}
        self.function_calls_count = {}

    def event_start_or_resume(self, event_key, current_time, call_stack):
        function_name = event_key.split(":")[1]
        if function_name in self.function_calls_count:
            self.function_calls_count[function_name] += 1
        else:
            self.function_calls_count[function_name] = 1

        call_info = {
            'start_time': current_time,
            'trace': list(call_stack),
            'nested_calls_time': 0,
            'exclusive_time': 0,
            'exceptions': [],
        }

        call_stack.append((event_key, call_info))
        self.function_metrics_out.setdefault(event_key, []).append(call_info)

    def event_return_or_yield(self, current_time, call_stack):
        if call_stack:
            _, call_info = call_stack.pop()
            self.update_call_info(call_info, current_time, call_stack)

    def event_exception(self, current_time, call_stack, exception):
        if call_stack:
            _, call_info = call_stack.pop()
            self.update_call_info(call_info, current_time, call_stack)
            call_info['exceptions'].append(exception)

    def update_call_info(self, call_info, current_time, call_stack):
        total_duration = current_time - call_info['start_time']
        exclusive_duration = max(0.000000000001, total_duration - call_info['nested_calls_time'])
        call_info.update({
            'exclusive_time': exclusive_duration,
        })
        if call_stack:
            parent_call = call_stack[-1][1]
            parent_call['nested_calls_time'] += total_duration

    def get_call_stack(self, thread_id):
        if thread_id not in self.call_stacks:
            self.call_stacks[thread_id] = self.call_stacks.get(self.thread_parents.get(thread_id), []).copy()
        return self.call_stacks[thread_id]

    def process_data(self):
        function_metrics = []
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'events.cache')
        with open(filepath, 'r') as file:
            lines = file.readlines()

        for line in lines:
            parts = line.strip().split(',')
            event_tuple = (parts[0], parts[1], float(parts[2]), parts[3])
            function_metrics.append(event_tuple)

        log.minor_success("Events loaded")

        for event in function_metrics:
            event_type, event_key, time, exception_var = event
            thread_id = event_key.split(":")[-1]
            if thread_id not in self.first_event_for_thread and event_type in {'PY_START', 'PY_RESUME'}:
                self.first_event_for_thread[thread_id] = event
                self.thread_parents[thread_id] = None
                for prev_event in function_metrics:
                    prev_thread_id = prev_event[1].split(":")[-1]
                    if thread_id != prev_thread_id:
                        self.thread_parents[thread_id] = prev_thread_id
                        break

            if thread_id not in self.thread_stacks:
                self.thread_stacks[thread_id] = []
                self.thread_stacks[thread_id].append(event_key)
            call_stack = self.get_call_stack(thread_id)
            self.thread_stacks[thread_id].append(call_stack.copy())

            if event_type in ['PY_START', 'PY_RESUME']:
                self.event_start_or_resume(event_key, time, call_stack)
            elif event_type in ['PY_RETURN', 'PY_YIELD']:
                for event_key_start in self.thread_stacks[thread_id]:
                    if event_key_start == event_key:
                        del self.thread_stacks[thread_id]
                self.event_return_or_yield(time, call_stack)
            elif event_type in ['PY_THROW', 'PY_UNWIND']:
                for event_key_start in self.thread_stacks[thread_id]:
                    if event_key_start == event_key:
                        del self.thread_stacks[thread_id]
                self.event_exception(time, call_stack, exception_var)

    def get_trace(self, call_stack):
        return [{'source': item[0], 'function': item[1], 'line': int(item[2])}
                for item in (part.split(':') for part in call_stack if part)]

    def get_resources(self):
        self.process_data()

        resources = []
        log.minor_success("Events processed")
        for key, calls in self.function_metrics_out.items():
            parts = key.split(':')
            for call in calls:
                resources.append({
                    "amount": float(call['exclusive_time']),
                    "uid": {
                        "source": parts[0],
                        "function": parts[1],
                        "line": int(parts[2])
                    },
                    "tid": parts[-1],
                    "type": "time",
                    "ncalls": self.function_calls_count[parts[1]],
                    "trace": self.get_trace([f"{t[0]}" for t in call['trace']]),
                    "exceptions": call['exceptions'],
                })
        return resources
