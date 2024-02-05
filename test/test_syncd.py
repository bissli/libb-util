import sys
import time

from libb import NonBlockingDelay


def seconds():
    """Get seconds"""
    return int(time.time())


def delay_s(delay):
    """Blocking delay in seconds"""
    t0 = seconds()
    while (seconds() - t0) < delay:
        continue


if __name__ == '__main__':

    print('With blocking delay:')
    print('Starting 5 second delay')
    delay_s(5)
    print('Starting 1 second delay')
    delay_s(1)

    print('With non-blocking delay:')
    d0, d1 = NonBlockingDelay(), NonBlockingDelay()
    while True:
        try:
            if d0.timeout():
                print('Starting 5 second delay')
                d0.delay(5)
            if d1.timeout():
                print('Starting 1 second delay')
                d1.delay(1)
        except KeyboardInterrupt:
            print('Ctrl-C pressed...')
            sys.exit()
