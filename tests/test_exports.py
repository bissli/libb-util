"""Contract pins for the native extension surface and the generated doc index.

Neither the set of names the Rust extension exports nor the internal
consistency of the documentation tables is asserted anywhere else, so a
kernel added or renamed on the Rust side, or a category left out of the
ordering, would otherwise ship silently.
"""
import types
from collections import Counter

from libb import _docs, _libb, _rust


def test_rust_stub_all_matches_extension_surface():
    """Verify _rust.py's __all__ is exactly the native extension's exports.

    Mutation: adding, renaming, or removing a #[pyfunction] in
        rust/src/python.rs without updating _rust.py, leaving the documented
        surface and the real one out of step.
    Oracle: dir() of the built extension module, derived independently of
        the stub module's own list.
    """
    surface = {name for name in dir(_libb) if not name.startswith('_')}
    assert set(_rust.__all__) == surface


def test_rust_stub_names_resolve_to_the_extension():
    """Verify every exported name is the native function, not the doc stub.

    The stubs in _rust.py have empty bodies, so a name left out of the
    trailing ``from libb._libb import ...`` lines returns None for every
    call instead of failing.

    Mutation: dropping a name from _rust.py's re-import lines while leaving
        its stub body and its __all__ entry in place.
    Oracle: the runtime type of each attribute - the extension supplies
        builtin_function_or_method, the shadowed stub supplies function.
    """
    stubbed = [name for name in _rust.__all__
               if isinstance(getattr(_rust, name), types.FunctionType)]
    assert not stubbed, f'still resolving to the empty doc stub: {stubbed}'


def test_docs_tables_agree_on_categories():
    """Verify _docs.py's three tables classify every module identically.

    docs/generate_api_index.py iterates CATEGORY_ORDER and looks each entry
    up in CATEGORY_SECTIONS, so a category present in the sections but
    absent from the ordering drops its whole block from index.rst silently.

    Mutation: adding a category to CATEGORY_SECTIONS without adding it to
        CATEGORY_ORDER, listing a module in a section that
        MODULE_CATEGORIES does not classify, or filing a module under a
        section that contradicts its MODULE_CATEGORIES entry.
    Oracle: the set relations between the three tables, each derived from
        the other two rather than restated.
    """
    sectioned = [module
                 for sections in _docs.CATEGORY_SECTIONS.values()
                 for _, _, modules in sections
                 for module in modules]

    assert set(_docs.CATEGORY_SECTIONS) == set(_docs.CATEGORY_ORDER)
    assert set(_docs.MODULE_CATEGORIES.values()) <= set(_docs.CATEGORY_ORDER)
    assert set(sectioned) == set(_docs.MODULE_CATEGORIES)
    assert [name for name, count in Counter(sectioned).items() if count > 1] == []

    for category, sections in _docs.CATEGORY_SECTIONS.items():
        for _, _, modules in sections:
            for module in modules:
                assert _docs.MODULE_CATEGORIES[module] == category, (
                    f'{module} is filed under {category} but classified as '
                    f'{_docs.MODULE_CATEGORIES[module]}')
