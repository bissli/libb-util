// Allow false positive from PyO3 macro expansion in proc-macro generated code
#![allow(clippy::useless_conversion)]

mod dictsort;
mod numparse;
mod python;

pub use python::_libb;
