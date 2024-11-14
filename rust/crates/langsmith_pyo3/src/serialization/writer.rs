use std::io::Error;

pub(super) struct BufWriter {
    buf: *mut u8,
    len: usize,
    cap: usize,
}

impl BufWriter {
    const DEFAULT_CAPACITY: usize = 1024;

    pub(super) fn new() -> Self {
        let buffer = Vec::with_capacity(Self::DEFAULT_CAPACITY);
        let (buf, len, cap) = buffer.into_raw_parts();
        Self { buf, len, cap }
    }

    pub(super) fn finish(mut self) -> Vec<u8> {
        let end_length = self.len + 1;
        if end_length >= self.cap {
            self.reserve_at_least_capacity(end_length);
        }

        // SAFETY: We just ensured there's enough room in the buffer.
        unsafe {
            core::ptr::write(self.buffer_ptr(), 0);
        }

        // Difference with orjson: Python doesn't count the terminating `'\0'` in the length
        // of the string, but `Vec<u8>` does. So orjson doesn't add one here, but we must
        // or else we'll get unsoundness and a memory safety violation.
        self.len = end_length;

        self.into_inner()
    }

    pub(super) fn into_inner(self) -> Vec<u8> {
        // SAFETY: We constructed the `Vec` in `Self::new()`,
        //         and maintained the `Vec` invariants throughout all `Self` methods.
        unsafe { Vec::from_raw_parts(self.buf, self.len, self.cap) }
    }

    fn buffer_ptr(&self) -> *mut u8 {
        // SAFETY: The length must be in bounds at all times, or else we've already violated
        //         another invariant elsewhere.
        unsafe { self.buf.add(self.len) }
    }

    #[inline]
    pub fn reserve_at_least_capacity(&mut self, cap: usize) {
        // SAFETY: The buffer used to be a vector, and is exclusively owned by us.
        //         The `&mut self` here guarantees there can't be another mutable reference to it.
        //         It's safe to turn it back into a `Vec` and ask the `Vec` to resize itself.
        unsafe {
            let mut v = Vec::from_raw_parts(self.buf, self.len, self.cap);
            v.reserve(cap - self.cap);
            (self.buf, self.len, self.cap) = v.into_raw_parts();
        }
    }
}

impl std::io::Write for BufWriter {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        let _ = self.write_all(buf);
        Ok(buf.len())
    }

    fn write_all(&mut self, buf: &[u8]) -> Result<(), Error> {
        let to_write = buf.len();
        let end_length = self.len + to_write;
        if end_length >= self.cap {
            self.reserve_at_least_capacity(end_length);
        }

        // SAFETY: We never expose pointers to our internal buffer through the API,
        //         so we couldn't have gotten an overlapping buffer here.
        unsafe {
            core::ptr::copy_nonoverlapping(buf.as_ptr(), self.buffer_ptr(), to_write);
        };
        self.len = end_length;

        Ok(())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

impl orjson::WriteExt for &mut BufWriter {
    #[inline(always)]
    fn as_mut_buffer_ptr(&mut self) -> *mut u8 {
        self.buffer_ptr()
    }

    #[inline(always)]
    fn reserve(&mut self, len: usize) {
        let end_length = self.len + len;
        if end_length >= self.cap {
            self.reserve_at_least_capacity(end_length);
        }
    }

    #[inline]
    fn has_capacity(&mut self, len: usize) -> bool {
        self.len + len <= self.cap
    }

    #[inline(always)]
    fn set_written(&mut self, len: usize) {
        self.len += len;
    }

    fn write_str(&mut self, val: &str) -> Result<(), Error> {
        let to_write = val.len();
        let end_length = self.len + to_write + 2;
        if end_length >= self.cap {
            self.reserve_at_least_capacity(end_length);
        }

        // SAFETY: We ensured there's enough room in the buffer. The write is non-overlapping
        //         because we never hand out pointers to our internal buffer via our API.
        unsafe {
            let ptr = self.buffer_ptr();
            core::ptr::write(ptr, b'"');
            core::ptr::copy_nonoverlapping(val.as_ptr(), ptr.add(1), to_write);
            core::ptr::write(ptr.add(to_write + 1), b'"');
        };
        self.len = end_length;
        Ok(())
    }

    /// # Safety
    ///
    /// The caller must ensure they've reserved sufficient space in advance.
    unsafe fn write_reserved_fragment(&mut self, val: &[u8]) -> Result<(), Error> {
        let to_write = val.len();
        // SAFETY: The write is non-overlapping because we never hand out pointers to
        //         our internal buffer via our API. We must have enough space since the caller
        //         is required to have made sure of that already.
        unsafe {
            core::ptr::copy_nonoverlapping(val.as_ptr(), self.buffer_ptr(), to_write);
        };
        self.len += to_write;
        Ok(())
    }

    /// # Safety
    ///
    /// The caller must ensure they've reserved sufficient space in advance.
    #[inline(always)]
    unsafe fn write_reserved_punctuation(&mut self, val: u8) -> Result<(), Error> {
        // SAFETY: We must have enough space since the caller
        //         is required to have made sure of that already.
        unsafe { core::ptr::write(self.buffer_ptr(), val) };
        self.len += 1;
        Ok(())
    }

    /// # Safety
    ///
    /// The caller must ensure they've reserved sufficient space in advance.
    #[inline(always)]
    unsafe fn write_reserved_indent(&mut self, len: usize) -> Result<(), Error> {
        // SAFETY: We must have enough space since the caller
        //         is required to have made sure of that already.
        unsafe {
            core::ptr::write_bytes(self.buffer_ptr(), b' ', len);
        };
        self.len += len;
        Ok(())
    }
}
