libb-util Documentation
=======================

A comprehensive collection of utility functions and classes designed to enhance
productivity and simplify common programming tasks in Python.

.. note::
   All utilities should be imported from the top-level ``libb`` package:

   .. code-block:: python

      from libb import Setting, compose, attrdict, timeout

Function Reference
------------------

Core Utilities
~~~~~~~~~~~~~~

**Configuration** - Settings and environment management

.. autosummary::
   :nosignatures:

   libb.Setting
   libb.ConfigOptions
   libb.load_options
   libb.configure_environment
   libb.patch_library_config
   libb.setting_unlocked
   libb.get_tempdir
   libb.get_vendordir
   libb.get_outputdir
   libb.get_localdir

**Classes** - Class manipulation and decorators

.. autosummary::
   :nosignatures:

   libb.attrs
   libb.include
   libb.singleton
   libb.memoize
   libb.classproperty
   libb.delegate
   libb.lazy_property
   libb.cachedstaticproperty
   libb.staticandinstancemethod
   libb.metadict
   libb.makecls
   libb.extend_instance
   libb.ultimate_type
   libb.catch_exception
   libb.ErrorCatcher

**Functions** - Function composition and decorators

.. autosummary::
   :nosignatures:

   libb.is_instance_method
   libb.find_decorators
   libb.compose
   libb.composable
   libb.copydoc
   libb.get_calling_function
   libb.repeat
   libb.timing
   libb.suppresswarning
   libb.MultiMethod
   libb.multimethod

**Iterators** - Iterator utilities and sequence operations

.. autosummary::
   :nosignatures:

   libb.chunked
   libb.chunked_even
   libb.collapse
   libb.compact
   libb.grouper
   libb.hashby
   libb.infinite_iterator
   libb.iscollection
   libb.isiterable
   libb.issequence
   libb.partition
   libb.peel
   libb.roundrobin
   libb.rpeel
   libb.unique
   libb.unique_iter
   libb.same_order
   libb.coalesce
   libb.getitem
   libb.backfill
   libb.backfill_iterdict
   libb.align_iterdict

**Text** - Text processing and encoding

.. autosummary::
   :nosignatures:

   libb.random_string
   libb.fix_text
   libb.underscore_to_camelcase
   libb.uncamel
   libb.strip_ascii
   libb.sanitize_vulgar_string
   libb.round_digit_string
   libb.parse_number
   libb.truncate
   libb.rotate
   libb.smart_base64
   libb.strtobool
   libb.fuzzy_search
   libb.is_numeric

**Formatting** - String and number formatting

.. autosummary::
   :nosignatures:

   libb.Percent
   libb.capitalize
   libb.capwords
   libb.commafy
   libb.fmt
   libb.format
   libb.format_phone
   libb.format_secondsdelta
   libb.format_timedelta
   libb.format_timeinterval
   libb.splitcap
   libb.titlecase

**Path** - Path and module utilities

.. autosummary::
   :nosignatures:

   libb.add_to_sys_path
   libb.cd
   libb.get_module_dir
   libb.scriptname

**Dictionaries** - Dictionary manipulation

.. autosummary::
   :nosignatures:

   libb.ismapping
   libb.invert
   libb.mapkeys
   libb.mapvals
   libb.flatten
   libb.unnest
   libb.replacekey
   libb.replaceattr
   libb.cmp
   libb.multikeysort
   libb.map
   libb.get_attrs
   libb.trace_key
   libb.trace_value
   libb.add_branch
   libb.merge_dict

**Module** - Module loading and manipulation

.. autosummary::
   :nosignatures:

   libb.OverrideModuleGetattr
   libb.get_module
   libb.get_class
   libb.get_subclasses
   libb.get_function
   libb.load_module
   libb.patch_load
   libb.patch_module
   libb.create_instance
   libb.create_mock_module
   libb.VirtualModule
   libb.create_virtual_module
   libb.get_packages_in_module
   libb.get_package_paths_in_module
   libb.import_non_local

**Type Definitions** - Type aliases

.. autosummary::
   :nosignatures:

   libb.FileLike
   libb.Attachable
   libb.Dimension

Collections
~~~~~~~~~~~

**Attribute Dictionaries** - Dict subclasses with attribute access

.. autosummary::
   :nosignatures:

   libb.attrdict
   libb.lazydict
   libb.emptydict
   libb.bidict
   libb.MutableDict
   libb.CaseInsensitiveDict

**Ordered Set** - Set with insertion order

.. autosummary::
   :nosignatures:

   libb.OrderedSet

**Heap** - Priority queue with custom comparator

.. autosummary::
   :nosignatures:

   libb.ComparableHeap

Input/Output
~~~~~~~~~~~~

**CSV/JSON** - Data serialization

.. autosummary::
   :nosignatures:

   libb.render_csv
   libb.CsvZip
   libb.iterable_to_stream
   libb.stream
   libb.json_load_byteified
   libb.json_loads_byteified
   libb.suppress_print
   libb.wrap_suppress_print

**Stream** - TTY and stream utilities

.. autosummary::
   :nosignatures:

   libb.is_tty
   libb.stream_is_tty

**Process** - Process management

.. autosummary::
   :nosignatures:

   libb.process_by_name
   libb.process_by_name_and_port
   libb.kill_proc

**Signals** - Signal handling

.. autosummary::
   :nosignatures:

   libb.SIGNAL_TRANSLATION_MAP
   libb.DelayedKeyboardInterrupt

**MIME** - MIME type utilities

.. autosummary::
   :nosignatures:

   libb.guess_type
   libb.guess_extension
   libb.magic_mime_from_buffer

**Directory** - File system operations

.. autosummary::
   :nosignatures:

   libb.mkdir_p
   libb.make_tmpdir
   libb.expandabspath
   libb.get_directory_structure
   libb.search
   libb.safe_move
   libb.save_file_tmpdir
   libb.get_dir_match
   libb.load_files
   libb.load_files_tmpdir
   libb.dir_to_dict
   libb.download_file
   libb.splitall
   libb.resplit

Specialized
~~~~~~~~~~~

**Statistics** - Math and statistics

.. autosummary::
   :nosignatures:

   libb.npfunc
   libb.avg
   libb.pct_change
   libb.diff
   libb.thresh
   libb.isnumeric
   libb.digits
   libb.numify
   libb.parse
   libb.nearest
   libb.covarp
   libb.covars
   libb.varp
   libb.vars
   libb.stddevp
   libb.stddevs
   libb.beta
   libb.correl
   libb.rsq
   libb.rtns
   libb.logrtns
   libb.weighted_average
   libb.linear_regression
   libb.distance_from_line
   libb.linterp
   libb.np_divide
   libb.safe_add
   libb.safe_diff
   libb.safe_divide
   libb.safe_mult
   libb.safe_round
   libb.safe_cmp
   libb.safe_min
   libb.safe_max
   libb.convert_mixed_numeral_to_fraction
   libb.convert_to_mixed_numeral
   libb.round_to_nearest
   libb.BBox
   libb.overlaps
   libb.push_apart
   libb.numpy_smooth
   libb.choose

**Threading** - Concurrency utilities

.. autosummary::
   :nosignatures:

   libb.asyncd
   libb.call_with_future
   libb.RateLimitedExecutor
   libb.TaskRequest
   libb.TaskResponse
   libb.threaded

**Synchronization** - Timing and synchronization

.. autosummary::
   :nosignatures:

   libb.syncd
   libb.NonBlockingDelay
   libb.delay
   libb.debounce
   libb.wait_until
   libb.timeout
   libb.Future

**Cryptography** - Encoding utilities

.. autosummary::
   :nosignatures:

   libb.base64file
   libb.kryptophy

**Geographic** - Coordinate transformations

.. autosummary::
   :nosignatures:

   libb.merc_x
   libb.merc_y

**Random** - OS-seeded random functions

.. autosummary::
   :nosignatures:

   libb.random_choice
   libb.random_int
   libb.random_sample
   libb.random_random

**Exceptions** - Error handling

.. autosummary::
   :nosignatures:

   libb.print_exception
   libb.try_else

**Charts** - Visualization

.. autosummary::
   :nosignatures:

   libb.numpy_timeseries_plot

**Pandas** - DataFrame utilities

.. autosummary::
   :nosignatures:

   libb.is_null
   libb.download_tzdata
   libb.downcast
   libb.fuzzymerge

**Web** - Web application utilities

.. autosummary::
   :nosignatures:

   libb.get_or_create
   libb.paged
   libb.rsleep
   libb.rand_retry
   libb.cors_webpy
   libb.cors_flask
   libb.authd
   libb.xsrf_token
   libb.xsrf_protected
   libb.valid_api_key
   libb.requires_api_key
   libb.make_url
   libb.prefix_urls
   libb.url_path_join
   libb.first_of_each
   libb.safe_join
   libb.local_or_static_join
   libb.inject_file
   libb.inject_image
   libb.build_breadcrumb
   libb.breadcrumbify
   libb.appmenu
   libb.scale
   libb.render_field
   libb.login_protected
   libb.userid_or_admin
   libb.manager_or_admin
   libb.logerror
   libb.validip6addr
   libb.validipaddr
   libb.validipport
   libb.validip
   libb.validaddr
   libb.urlquote
   libb.httpdate
   libb.parsehttpdate
   libb.htmlquote
   libb.htmlunquote
   libb.websafe
   libb.JSONEncoderISODate
   libb.JSONDecoderISODate
   libb.ProfileMiddleware
   libb.COOKIE_DEFAULTS

**Windows** - Windows-specific utilities

.. autosummary::
   :nosignatures:

   libb.run_command
   libb.psexec_session
   libb.file_share_session
   libb.mount_admin_share
   libb.mount_file_share
   libb.parse_wmic_output
   libb.exit_cmd

----

Design Philosophy
-----------------

- **Transparent API**: Always import from top-level ``libb``, never from submodules
- **Graceful Dependencies**: Optional dependencies wrapped for clean imports
- **Short, Singular Names**: Modules use concise names (e.g., ``func`` not ``funcutils``)
- **Comprehensive Exports**: All modules explicitly define their public API via ``__all__``

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index
   api/core
   api/collections
   api/io
   api/specialized

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
