"""Documentation metadata for auto-generating Sphinx index.

This module contains category mappings used by the documentation generator
to organize exports from each module into the appropriate sections.
"""

__all__ = ['MODULE_CATEGORIES', 'CATEGORY_ORDER', 'CATEGORY_SECTIONS']

# Maps module names to their documentation category
MODULE_CATEGORIES = {
    # Core Utilities
    'config': 'Core',
    'classes': 'Core',
    'func': 'Core',
    'iter': 'Core',
    'text': 'Core',
    'format': 'Core',
    'path': 'Core',
    'dicts': 'Core',
    'module': 'Core',
    'typedefs': 'Core',
    # Collections
    'attrdict': 'Collections',
    'orderedset': 'Collections',
    'heap': 'Collections',
    # I/O
    'iolib': 'I/O',
    'stream': 'I/O',
    'proc': 'I/O',
    'signals': 'I/O',
    'mime': 'I/O',
    'dir': 'I/O',
    # Specialized
    'stats': 'Specialized',
    'thread': 'Specialized',
    'sync': 'Specialized',
    'crypto': 'Specialized',
    'geo': 'Specialized',
    'rand': 'Specialized',
    'exception': 'Specialized',
    'chart': 'Specialized',
    'pandasutils': 'Specialized',
    'webapp': 'Specialized',
    'win': 'Specialized',
}

# Order in which categories appear in the documentation
CATEGORY_ORDER = ['Core', 'Collections', 'I/O', 'Specialized']

# Maps categories to their section headers and subsections
# Each subsection has: (title, description, module_names)
CATEGORY_SECTIONS = {
    'Core': [
        ('Configuration', 'Settings and environment management', ['config']),
        ('Classes', 'Class manipulation and decorators', ['classes']),
        ('Functions', 'Function composition and decorators', ['func']),
        ('Iterators', 'Iterator utilities and sequence operations', ['iter']),
        ('Text', 'Text processing and encoding', ['text']),
        ('Formatting', 'String and number formatting', ['format']),
        ('Path', 'Path and module utilities', ['path']),
        ('Dictionaries', 'Dictionary manipulation', ['dicts']),
        ('Module', 'Module loading and manipulation', ['module']),
        ('Type Definitions', 'Type aliases', ['typedefs']),
    ],
    'Collections': [
        ('Attribute Dictionaries', 'Dict subclasses with attribute access', ['attrdict']),
        ('Ordered Set', 'Set with insertion order', ['orderedset']),
        ('Heap', 'Priority queue with custom comparator', ['heap']),
    ],
    'I/O': [
        ('CSV/JSON', 'Data serialization', ['iolib']),
        ('Stream', 'TTY and stream utilities', ['stream']),
        ('Process', 'Process management', ['proc']),
        ('Signals', 'Signal handling', ['signals']),
        ('MIME', 'MIME type utilities', ['mime']),
        ('Directory', 'File system operations', ['dir']),
    ],
    'Specialized': [
        ('Statistics', 'Math and statistics', ['stats']),
        ('Threading', 'Concurrency utilities', ['thread']),
        ('Synchronization', 'Timing and synchronization', ['sync']),
        ('Cryptography', 'Encoding utilities', ['crypto']),
        ('Geographic', 'Coordinate transformations', ['geo']),
        ('Random', 'OS-seeded random functions', ['rand']),
        ('Exceptions', 'Error handling', ['exception']),
        ('Charts', 'Visualization', ['chart']),
        ('Pandas', 'DataFrame utilities', ['pandasutils']),
        ('Web', 'Web application utilities', ['webapp']),
        ('Windows', 'Windows-specific utilities', ['win']),
    ],
}
