"""Contracts that keep a bare `pip install libb-util` importable.

Every module `libb/__init__.py` star-imports runs at import time, so an
undeclared third-party import in any of them makes the whole package
unimportable for anyone who installed only the declared dependencies. The
development environment never sees it, because the dev extras pull the
missing distribution in transitively.

Optional dependencies are imported inside the function that needs them
(``chart.py`` does this with matplotlib); module level is reserved for
declared ones.
"""
import ast
import datetime
import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'libb'
PYPROJECT = pathlib.Path(__file__).resolve().parent.parent / 'pyproject.toml'

# Distributions whose import name differs from the name pip installs.
DIST_TO_MODULE = {
    'python-dateutil': 'dateutil',
    'more-itertools': 'more_itertools',
    'trace-dkey': 'trace_dkey',
    'typing-extensions': 'typing_extensions',
    'pyyaml': 'yaml',
    'pillow': 'PIL',
    }


def star_imported_modules():
    """Names of the submodules ``__init__.py`` star-imports, in file order."""
    init = (SRC / '__init__.py').read_text()
    return re.findall(r'^from libb\.(\w+) import \*', init, re.M)


def declared_base_modules():
    """Import names of the distributions in ``[project] dependencies``."""
    text = PYPROJECT.read_text()
    block = text[text.index('dependencies = ['):]
    block = block[:block.index(']')]
    names = [re.split(r'[<>=!~ ]', line.strip().strip('",'))[0].lower()
             for line in block.splitlines()[1:] if line.strip()]
    return {DIST_TO_MODULE.get(name, name.replace('-', '_')) for name in names}


def test_star_imported_modules_declare_their_imports():
    """Verify no star-imported module imports an undeclared package at import time.

    Mutation: adding a module-level ``from dateutil import parser`` to a
        star-imported module without adding python-dateutil to
        [project] dependencies - which made 0.0.45 and 0.0.46 raise
        ModuleNotFoundError on ``import libb`` for a bare install.
    Oracle: the declared dependency list parsed from pyproject.toml,
        compared against the module-level imports found by ast.
    """
    declared = declared_base_modules()
    offenders = {}
    for name in star_imported_modules():
        tree = ast.parse((SRC / f'{name}.py').read_text())
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported = [node.module.split('.')[0]]
            else:
                continue
            for module in imported:
                if module in sys.stdlib_module_names or module == 'libb':
                    continue
                if module not in declared:
                    offenders[module] = f'{name}.py:{node.lineno}'

    assert not offenders, (
        'undeclared module-level imports (declare them in [project] '
        f'dependencies, or move them into the function that needs them): {offenders}')


def test_json_iso_decoder_leaves_non_dates_alone():
    """Verify the decoder reads ISO dates only and leaves other strings.

    The hook once ran dateutil.parser.parse over every string value, so
    '10' and 'March' became datetimes with today's date filled in and the
    same payload decoded differently on different days.

    Mutation: restoring a lenient parser, or dropping the isinstance
        guard so a non-str value reaches fromisoformat.
    Oracle: hand-listed strings, each its own input.
    """
    from libb.webapp import JSONDecoderISODate

    decoded = JSONDecoderISODate().decode(
        '{"qty": "10", "note": "March", "code": "T", "when": "2014-10-02",'
        ' "at": "10:30:00", "n": 7}')
    assert decoded['qty'] == '10'
    assert decoded['note'] == 'March'
    assert decoded['code'] == 'T'
    assert decoded['when'] == datetime.datetime(2014, 10, 2, 0, 0)
    assert decoded['at'] == '10:30:00'
    assert decoded['n'] == 7


def test_json_iso_decoder_reads_basic_format_dates():
    """Pin the one numeric string the decoder still converts.

    An 8-digit string is ISO 8601 basic format, so fromisoformat reads it
    as a date. This is the deliberate edge of the contract above, not an
    oversight: a caller storing 8-digit ids as strings gets dates back.

    Mutation: widening the decoder to any numeric string, or narrowing it
        to the extended form and breaking basic-format payloads.
    Oracle: hand-computed date for the 8-digit case, and the 4- and
        6-digit neighbors that must stay strings.
    """
    from libb.webapp import JSONDecoderISODate

    decoded = JSONDecoderISODate().decode(
        '{"a": "20141002", "b": "2024", "c": "201410"}')
    assert decoded['a'] == datetime.datetime(2014, 10, 2, 0, 0)
    assert decoded['b'] == '2024'
    assert decoded['c'] == '201410'


def test_json_iso_encoder_writes_a_time():
    """Verify a time encodes to ISO rather than raising.

    Mutation: dropping datetime.time from the isinstance tuple, which
        takes the encoder back to raising TypeError on a time value.
    Oracle: hand-written ISO strings.
    """
    from libb.webapp import JSONEncoderISODate

    assert JSONEncoderISODate().encode(
        {'t': datetime.time(10, 30)}) == '{"t": "10:30:00"}'
    assert JSONEncoderISODate().encode(
        {'t': datetime.time(10, 30, 5, 250)}) == '{"t": "10:30:05.000250"}'


def test_json_iso_date_round_trips():
    """Verify the encoder/decoder pair still round-trips a date and a datetime.

    Mutation: tightening the decoder past what isoformat() emits, e.g.
        rejecting a date-only string or a microsecond component, which
        would break the pairing with JSONEncoderISODate.
    Oracle: values encoded by JSONEncoderISODate itself, decoded back.
    """
    from libb.webapp import JSONDecoderISODate, JSONEncoderISODate

    for value, expected in [
            (datetime.date(2014, 10, 2), datetime.datetime(2014, 10, 2, 0, 0)),
            (datetime.datetime(2014, 10, 2, 13, 45, 6), datetime.datetime(2014, 10, 2, 13, 45, 6)),
            (datetime.datetime(2014, 10, 2, 13, 45, 6, 7890),
             datetime.datetime(2014, 10, 2, 13, 45, 6, 7890)),
            ]:
        payload = JSONEncoderISODate().encode({'dt': value})
        assert JSONDecoderISODate().decode(payload) == {'dt': expected}, payload
