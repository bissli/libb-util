// Allow false positive from PyO3 macro expansion in proc-macro generated code
#![allow(clippy::useless_conversion)]

#[cfg(feature = "python")]
mod dictsort;
#[cfg(feature = "python")]
mod iter;
pub mod numparse;
#[cfg(feature = "python")]
mod python;
pub mod text;
#[cfg(test)]
mod vectors;

#[cfg(feature = "python")]
pub use python::_libb;
