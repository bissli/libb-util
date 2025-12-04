import os
import signal

__all__ = [
    'SIGNAL_TRANSLATION_MAP',
    'DelayedKeyboardInterrupt',
]


class _SignalMap(dict):
    """Map of signal numbers to signal names."""


SIGNAL_TRANSLATION_MAP = _SignalMap({signal.SIGINT: 'SIGINT', signal.SIGTERM: 'SIGTERM'})

# Alias for internal use
SIGMAP = SIGNAL_TRANSLATION_MAP


class DelayedKeyboardInterrupt:
    """Context manager that suppresses SIGINT & SIGTERM during a block.

    Signal handlers are called on exit from the block.

    .. note::
        Inspired by https://stackoverflow.com/a/21919644

    :param propagate_to_forked_processes: Controls behavior in forked processes:
        - True: Same behavior as parent process
        - False: Use original signal handler
        - None: Ignore signals (default)
    """

    def __init__(self, propagate_to_forked_processes=None):
        self._pid = os.getpid()
        self._propagate_to_forked_processes = propagate_to_forked_processes
        self._sig = None
        self._frame = None
        self._old_signal_handler_map = None

    def __enter__(self):
        self._old_signal_handler_map = {sig: signal.signal(sig, self._handler) for sig, _ in SIGMAP.items()}

    def __exit__(self, exc_type, exc_val, exc_tb):
        for sig, handler in self._old_signal_handler_map.items():
            signal.signal(sig, handler)

        if self._sig is None:
            return

        self._old_signal_handler_map[self._sig](self._sig, self._frame)

    def _handler(self, sig, frame):
        self._sig = sig
        self._frame = frame

        # protection against fork.
        if os.getpid() != self._pid:
            if self._propagate_to_forked_processes is False:
                print(f'!!! DelayedKeyboardInterrupt._handler: {SIGMAP[sig]} received; '
                      f'PID mismatch: {os.getpid()=}, {self._pid=}, calling original handler')
                self._old_signal_handler_map[self._sig](self._sig, self._frame)
            elif self._propagate_to_forked_processes is None:
                print(f'!!! DelayedKeyboardInterrupt._handler: {SIGMAP[sig]} received; '
                      f'PID mismatch: {os.getpid()=}, ignoring the signal')
                return

        print(f'!!! DelayedKeyboardInterrupt._handler: {SIGMAP[sig]} received; delaying KeyboardInterrupt')


if __name__ == '__main__':
    # Test code
    with DelayedKeyboardInterrupt():
        import os
        import sys
        try:
            sys.exit(0)
        finally:
            print('Done!')
