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
   >>> import libb
   >>> _ = testmod(libb.collections._set)
   >>> _ = testmod(libb.collections._dict)
   >>> _ = testmod(libb.collections._heap)
   >>> _ = testmod(libb.formatutils)
   >>> _ = testmod(libb.moduleutils)
   >>> _ = testmod(libb.webutils)
   >>> _ = testmod(libb.funcutils)
   >>> _ = testmod(libb.mathutils)
   >>> _ = testmod(libb.pathutils)
   >>> _ = testmod(libb.dictutils)
   >>> _ = testmod(libb.funcutils)
   >>> _ = testmod(libb.mimetypesutils)
   >>> _ = testmod(libb.streamutils)
   >>> _ = testmod(libb.typingutils)
   >>> _ = testmod(libb.classutils)
   >>> _ = testmod(libb.matrixutils)
