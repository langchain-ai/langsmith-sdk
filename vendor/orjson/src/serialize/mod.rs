// SPDX-License-Identifier: (Apache-2.0 OR MIT)

mod buffer;
mod error;
mod obtype;
mod per_type;
mod serializer;
mod state;
mod writer;

pub use serializer::{serialize, PyObjectSerializer};
pub use state::SerializerState;
pub use writer::{to_writer, WriteExt};
