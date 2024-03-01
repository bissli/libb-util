"""Used in logging colorized handler"""

import sys
from contextlib import contextmanager

from libb import config

#
# use colorama wrappers around python stdlib ctypes on Windows
#
if config.WIN:
    import colorama
    colorama.just_fix_windows_console()
    from colorama.win32 import (
        STDERR,
        STDOUT,
        GetConsoleScreenBufferInfo,
        SetConsoleTextAttribute,
    )

    NT_CONSOLE_HANDLE = {1: STDOUT, 2: STDERR}

#
# windows color codes
#
Fore = {'Black': 0, 'Blue': 1, 'Green': 2, 'Red': 4}
Fore['Cyan'] = Fore['Blue'] | Fore['Green']
Fore['Magenta'] = Fore['Red'] | Fore['Blue']
Fore['Yellow'] = Fore['Red'] | Fore['Green']
Fore['White'] = Fore['Red'] | Fore['Green'] | Fore['Blue']
for k, v in list(Fore.items()):
    Fore['Bright' + k] = 8 | v
Back = {k: v << 4 for k, v in Fore.items()}


#
# windows color api constants
#
FOREGROUND_BLUE = 0x0001   # text color blue
FOREGROUND_GREEN = 0x0002   # text color green
FOREGROUND_RED = 0x0004   # text color red
FOREGROUND_INTENSITY = 0x0008   # text intensified
FOREGROUND_WHITE = FOREGROUND_BLUE | FOREGROUND_GREEN | FOREGROUND_RED


# winbase.h
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12


# wincon.h
FOREGROUND_BLACK = 0x0000
FOREGROUND_BLUE = 0x0001
FOREGROUND_GREEN = 0x0002
FOREGROUND_CYAN = 0x0003
FOREGROUND_RED = 0x0004
FOREGROUND_MAGENTA = 0x0005
FOREGROUND_YELLOW = 0x0006
FOREGROUND_GREY = 0x0007
FOREGROUND_INTENSITY = 0x0008   # foreground intensified

BACKGROUND_BLACK = 0x0000
BACKGROUND_BLUE = 0x0010
BACKGROUND_GREEN = 0x0020
BACKGROUND_CYAN = 0x0030
BACKGROUND_RED = 0x0040
BACKGROUND_MAGENTA = 0x0050
BACKGROUND_YELLOW = 0x0060
BACKGROUND_GREY = 0x0070
BACKGROUND_INTENSITY = 0x0080   # background intensified


#
# ansi color constants (non windows)
#
ANSI_RED = '\x1b[31m'
ANSI_YELLOW = '\x1b[33m'
ANSI_GREEN = '\x1b[32m'
ANSI_PINK = '\x1b[35m'
ANSI_NORMAL = '\x1b[0m'
ANSI_CLEAR = '\x1b[m'


def choose_color_windows(levelno):
    if levelno >= 50:
        color = BACKGROUND_YELLOW | FOREGROUND_RED | FOREGROUND_INTENSITY | BACKGROUND_INTENSITY
    elif levelno >= 40:
        color = FOREGROUND_RED | FOREGROUND_INTENSITY
    elif levelno >= 30:
        color = FOREGROUND_YELLOW | FOREGROUND_INTENSITY
    elif levelno >= 20:
        color = FOREGROUND_GREEN
    elif levelno >= 10:
        color = FOREGROUND_MAGENTA
    else:
        color = FOREGROUND_WHITE
    return color


def choose_color_ansi(levelno):
    if levelno >= 50:
        color = ANSI_RED
    elif levelno >= 40:
        color = ANSI_RED
    elif levelno >= 30:
        color = ANSI_YELLOW
    elif levelno >= 20:
        color = ANSI_GREEN
    elif levelno >= 10:
        color = ANSI_PINK
    else:
        color = ANSI_NORMAL
    return color


@contextmanager
def set_color(color, stream=sys.stdout):
    """Set the color on the stream temporarily; only necessary on Windows"""
    if config.WIN:
        handle = NT_CONSOLE_HANDLE[stream.fileno()]
        default = GetConsoleScreenBufferInfo(handle).wAttributes
        try:
            SetConsoleTextAttribute(handle, color)
            yield
        finally:
            SetConsoleTextAttribute(handle, default)
    else:
        try:
            stream.write(color)
            yield
        except:
            stream.write(ANSI_CLEAR)
            raise
        finally:
            stream.write(ANSI_CLEAR)


def write_color(color, message, stream=sys.stdout):
    """Just a clean DRY way to write stream and the close"""
    with set_color(color, stream):
        stream.write(message)


if __name__ == '__main__':
    if config.WIN:
        for k in range(256):
            write_color(k, f'This is color {k}. How does it look?\n')
        print('Auto-reset!')
        for k, v in sorted(Fore.items()):
            with set_color(v):
                print(k)
    else:
        for k in range(256):
            color = choose_color_ansi(k)
            print(f'{color}This is color {k}. How does it look?\n{color}')
        color = choose_color_ansi(-1)
        print(f'{color}Reset!{color}')
