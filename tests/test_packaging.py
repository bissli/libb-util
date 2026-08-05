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


def test_json_iso_decoder_currently_coerces_non_dates():
    """Pin the decoder's lenient parsing, which rewrites ordinary strings.

    Despite the ISODate name, the object hook runs dateutil.parser.parse
    over EVERY string value in the payload, so '10' and 'March' become
    datetimes with today's date filled in. That is a real hazard for any
    caller decoding arbitrary JSON, but it is the shipped behaviour and
    narrowing it is a semantic decision, not a packaging fix - notably
    datetime.fromisoformat is not a drop-in replacement, since it rejects
    'Z' suffixes on Python 3.10 and non-ISO formats on every version.

    This is a characterisation pin, not an endorsement: it exists so that
    tightening the parser fails here and forces the change to be deliberate.

    Mutation: swapping the parser for a stricter or a differently-lenient
        one without deciding what the decoder is contracted to accept.
    Oracle: the current build's own output for strings that are not dates.
    """
    from libb.webapp import JSONDecoderISODate
    decoded = JSONDecoderISODate().decode('{"qty": "10", "note": "March", "code": "T"}')
    assert isinstance(decoded['qty'], datetime.datetime), (
        'lenient parsing stopped coercing a bare integer string; if that was '
        'intended, retire this pin and document the new contract')
    assert isinstance(decoded['note'], datetime.datetime)
    assert decoded['code'] == 'T'


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
