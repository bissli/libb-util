.. desc:: Files with doctests to include in the pytest runner

.. doctest::
   >>> from importlib import util as importlib_util
   >>> def load_module(name, path):
   ...     module_spec = importlib_util.spec_from_file_location(name, path)
   ...     module = importlib_util.module_from_spec(module_spec)
   ...     module_spec.loader.exec_module(module)
   ...     return module
   >>> from functools import partial
   >>> import doctest
   >>> testmod = partial(doctest.testmod, verbose=False, optionflags=4 | 8 | 32)

   libb modules
   >>> import sys
   >>> from libb import orderedset, attrdict, heap, format, module, webapp, func, stats, path, dicts, mime, stream, typing, classes, matrix
   >>> _ = testmod(sys.modules['libb.orderedset'])
   >>> _ = testmod(sys.modules['libb.attrdict'])
   >>> _ = testmod(sys.modules['libb.heap'])
   >>> _ = testmod(sys.modules['libb.format'])
   >>> _ = testmod(sys.modules['libb.module'])
   >>> _ = testmod(sys.modules['libb.webapp'])
   >>> _ = testmod(sys.modules['libb.func'])
   >>> _ = testmod(sys.modules['libb.stats'])
   >>> _ = testmod(sys.modules['libb.path'])
   >>> _ = testmod(sys.modules['libb.dicts'])
   >>> _ = testmod(sys.modules['libb.func'])
   >>> _ = testmod(sys.modules['libb.mime'])
   >>> _ = testmod(sys.modules['libb.stream'])
   >>> _ = testmod(sys.modules['libb.typing'])
   >>> _ = testmod(sys.modules['libb.classes'])
   >>> _ = testmod(sys.modules['libb.matrix'])
