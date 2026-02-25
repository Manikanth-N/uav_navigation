from collections import defaultdict
import threading

class EventEmitter:
    def __init__(self):
        self._callbacks = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event_name, callback):
        with self._lock:
            self._callbacks[event_name].append(callback)

    def emit(self, event_name, *args, **kwargs):
        with self._lock:
            callbacks = list(self._callbacks[event_name])

        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                print(f"⚠ Callback error in '{event_name}': {e}")