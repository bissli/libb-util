import logging

__all__ = ['StderrStreamLogger']


class StderrStreamLogger:
    """Patch over stderr to log print statements to INFO
    placeholders isatty and fileno mimic python stream
    stderr still accessible at stderr.__stderr__
    """

    def __init__(self, logger):
        self.logger = logger
        self.level = logging.INFO
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def isatty(self):
        return False

    def fileno(self):
        return None


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
