class Dispatcher:

    def __init__(self):
        self._listeners = {}
        self._latest = {}

    def register(self, msg_type, callback):
        if msg_type not in self._listeners:
            self._listeners[msg_type] = []
        self._listeners[msg_type].append(callback)

    def dispatch(self, msg):
        msg_type = msg.get_type()

        # Save latest message
        self._latest[msg_type] = msg

        # Call listeners
        if msg_type in self._listeners:
            for cb in self._listeners[msg_type]:
                cb(msg)

    def latest(self, msg_type):
        return self._latest.get(msg_type)