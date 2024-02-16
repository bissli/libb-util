.. desc:: Files with doctests to include in the pytest runner

.. doctest::
   >>> import libb
   >>> from functools import partial
   >>> import doctest
   >>> flags = doctest.NORMALIZE_WHITESPACE \
   ...  | doctest.IGNORE_EXCEPTION_DETAIL \
   ...  | doctest.ELLIPSIS
   >>> testmod = partial(doctest.testmod, verbose=False, optionflags=flags)

   libb modules
   >>> _ = testmod(libb.format)
   >>> _ = testmod(libb.date)
   >>> _ = testmod(libb.config)
   >>> _ = testmod(libb.weblib)
   >>> _ = testmod(libb.mail)
   >>> _ = testmod(libb.util)
   >>> _ = testmod(libb.maths)
   >>> _ = testmod(libb.text)
   >>> _ = testmod(libb.dir)
   >>> _ = testmod(libb.module)
   >>> _ = testmod(libb.cmdline)
   >>> _ = testmod(libb.path)
   >>> _ = testmod(libb.io)
