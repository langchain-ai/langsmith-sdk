// SPDX-License-Identifier: (Apache-2.0 OR MIT)

#[cfg(all(not(feature = "unstable-simd"), not(target_arch = "x86_64")))]
use super::escape::{NEED_ESCAPED, QUOTE_TAB};

macro_rules! impl_format_scalar {
    ($dst:expr, $src:expr, $value_len:expr) => {
        unsafe {
            for _ in 0..$value_len {
                core::ptr::write($dst, *($src));
                $src = $src.add(1);
                $dst = $dst.add(1);
                if unlikely!(NEED_ESCAPED[*($src.sub(1)) as usize] > 0) {
                    let escape = QUOTE_TAB[*($src.sub(1)) as usize];
                    write_escape!(escape, $dst.sub(1));
                    $dst = $dst.add(escape.1 as usize - 1);
                }
            }
        }
    };
}

#[cfg(all(not(feature = "unstable-simd"), not(target_arch = "x86_64")))]
pub unsafe fn format_escaped_str_scalar(
    odst: *mut u8,
    value_ptr: *const u8,
    value_len: usize,
) -> usize {
    let mut dst = odst;
    let mut src = value_ptr;

    core::ptr::write(dst, b'"');
    dst = dst.add(1);

    impl_format_scalar!(dst, src, value_len);

    core::ptr::write(dst, b'"');
    dst = dst.add(1);

    dst as usize - odst as usize
}
