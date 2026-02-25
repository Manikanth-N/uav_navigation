# src/uav_sdk/core/state.py

class UAVState:

    def __init__(self):
        self._data = {}
        self._callbacks = {}

    # Register callback
    def on(self, key, callback):
        self._callbacks.setdefault(key, []).append(callback)

    # Get value
    def get(self, key):
        return self._data.get(key)

    # Update value and trigger callbacks if changed
    def update(self, key, value):
        old = self._data.get(key)

        if old == value:
            return

        self._data[key] = value

        # Fire callbacks
        for cb in self._callbacks.get(key, []):
            cb(value)