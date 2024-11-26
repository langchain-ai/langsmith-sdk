use std::iter::FusedIterator;

use crate::err::{self, PyResult};
use crate::ffi::{self, Py_ssize_t};
use crate::ffi_ptr_ext::FfiPtrExt;
use crate::internal_tricks::get_ssize_index;
use crate::types::{PySequence, PyTuple};
use crate::{Borrowed, Bound, BoundObject, IntoPyObject, PyAny, PyErr, PyObject, Python};

use crate::types::any::PyAnyMethods;
use crate::types::sequence::PySequenceMethods;

/// Represents a Python `list`.
///
/// Values of this type are accessed via PyO3's smart pointers, e.g. as
/// [`Py<PyList>`][crate::Py] or [`Bound<'py, PyList>`][Bound].
///
/// For APIs available on `list` objects, see the [`PyListMethods`] trait which is implemented for
/// [`Bound<'py, PyDict>`][Bound].
#[repr(transparent)]
pub struct PyList(PyAny);

pyobject_native_type_core!(PyList, pyobject_native_static_type_object!(ffi::PyList_Type), #checkfunction=ffi::PyList_Check);

#[inline]
#[track_caller]
pub(crate) fn new_from_iter(
    py: Python<'_>,
    elements: impl ExactSizeIterator<Item = PyObject>,
) -> Bound<'_, PyList> {
    try_new_from_iter(py, elements.map(|e| e.into_bound(py)).map(Ok)).unwrap()
}

#[inline]
#[track_caller]
pub(crate) fn try_new_from_iter<'py>(
    py: Python<'py>,
    mut elements: impl ExactSizeIterator<Item = PyResult<Bound<'py, PyAny>>>,
) -> PyResult<Bound<'py, PyList>> {
    unsafe {
        // PyList_New checks for overflow but has a bad error message, so we check ourselves
        let len: Py_ssize_t = elements
            .len()
            .try_into()
            .expect("out of range integral type conversion attempted on `elements.len()`");

        let ptr = ffi::PyList_New(len);

        // We create the `Bound` pointer here for two reasons:
        // - panics if the ptr is null
        // - its Drop cleans up the list if user code or the asserts panic.
        let list = ptr.assume_owned(py).downcast_into_unchecked();

        let count = (&mut elements)
            .take(len as usize)
            .try_fold(0, |count, item| {
                #[cfg(not(Py_LIMITED_API))]
                ffi::PyList_SET_ITEM(ptr, count, item?.into_ptr());
                #[cfg(Py_LIMITED_API)]
                ffi::PyList_SetItem(ptr, count, item?.into_ptr());
                Ok::<_, PyErr>(count + 1)
            })?;

        assert!(elements.next().is_none(), "Attempted to create PyList but `elements` was larger than reported by its `ExactSizeIterator` implementation.");
        assert_eq!(len, count, "Attempted to create PyList but `elements` was smaller than reported by its `ExactSizeIterator` implementation.");

        Ok(list)
    }
}

impl PyList {
    /// Constructs a new list with the given elements.
    ///
    /// If you want to create a [`PyList`] with elements of different or unknown types, or from an
    /// iterable that doesn't implement [`ExactSizeIterator`], use [`PyListMethods::append`].
    ///
    /// # Examples
    ///
    /// ```rust
    /// use pyo3::prelude::*;
    /// use pyo3::types::PyList;
    ///
    /// # fn main() -> PyResult<()> {
    /// Python::with_gil(|py| {
    ///     let elements: Vec<i32> = vec![0, 1, 2, 3, 4, 5];
    ///     let list = PyList::new(py, elements)?;
    ///     assert_eq!(format!("{:?}", list), "[0, 1, 2, 3, 4, 5]");
    /// # Ok(())
    /// })
    /// # }
    /// ```
    ///
    /// # Panics
    ///
    /// This function will panic if `element`'s [`ExactSizeIterator`] implementation is incorrect.
    /// All standard library structures implement this trait correctly, if they do, so calling this
    /// function with (for example) [`Vec`]`<T>` or `&[T]` will always succeed.
    #[track_caller]
    pub fn new<'py, T, U>(
        py: Python<'py>,
        elements: impl IntoIterator<Item = T, IntoIter = U>,
    ) -> PyResult<Bound<'py, PyList>>
    where
        T: IntoPyObject<'py>,
        U: ExactSizeIterator<Item = T>,
    {
        let iter = elements.into_iter().map(|e| {
            e.into_pyobject(py)
                .map(BoundObject::into_any)
                .map(BoundObject::into_bound)
                .map_err(Into::into)
        });
        try_new_from_iter(py, iter)
    }

    /// Deprecated name for [`PyList::new`].
    #[deprecated(since = "0.23.0", note = "renamed to `PyList::new`")]
    #[allow(deprecated)]
    #[inline]
    #[track_caller]
    pub fn new_bound<T, U>(
        py: Python<'_>,
        elements: impl IntoIterator<Item = T, IntoIter = U>,
    ) -> Bound<'_, PyList>
    where
        T: crate::ToPyObject,
        U: ExactSizeIterator<Item = T>,
    {
        Self::new(py, elements.into_iter().map(|e| e.to_object(py))).unwrap()
    }

    /// Constructs a new empty list.
    pub fn empty(py: Python<'_>) -> Bound<'_, PyList> {
        unsafe {
            ffi::PyList_New(0)
                .assume_owned(py)
                .downcast_into_unchecked()
        }
    }

    /// Deprecated name for [`PyList::empty`].
    #[deprecated(since = "0.23.0", note = "renamed to `PyList::empty`")]
    #[inline]
    pub fn empty_bound(py: Python<'_>) -> Bound<'_, PyList> {
        Self::empty(py)
    }
}

/// Implementation of functionality for [`PyList`].
///
/// These methods are defined for the `Bound<'py, PyList>` smart pointer, so to use method call
/// syntax these methods are separated into a trait, because stable Rust does not yet support
/// `arbitrary_self_types`.
#[doc(alias = "PyList")]
pub trait PyListMethods<'py>: crate::sealed::Sealed {
    /// Returns the length of the list.
    fn len(&self) -> usize;

    /// Checks if the list is empty.
    fn is_empty(&self) -> bool;

    /// Returns `self` cast as a `PySequence`.
    fn as_sequence(&self) -> &Bound<'py, PySequence>;

    /// Returns `self` cast as a `PySequence`.
    fn into_sequence(self) -> Bound<'py, PySequence>;

    /// Gets the list item at the specified index.
    /// # Example
    /// ```
    /// use pyo3::{prelude::*, types::PyList};
    /// Python::with_gil(|py| {
    ///     let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
    ///     let obj = list.get_item(0);
    ///     assert_eq!(obj.unwrap().extract::<i32>().unwrap(), 2);
    /// });
    /// ```
    fn get_item(&self, index: usize) -> PyResult<Bound<'py, PyAny>>;

    /// Gets the list item at the specified index. Undefined behavior on bad index. Use with caution.
    ///
    /// # Safety
    ///
    /// Caller must verify that the index is within the bounds of the list.
    #[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED)))]
    unsafe fn get_item_unchecked(&self, index: usize) -> Bound<'py, PyAny>;

    /// Takes the slice `self[low:high]` and returns it as a new list.
    ///
    /// Indices must be nonnegative, and out-of-range indices are clipped to
    /// `self.len()`.
    fn get_slice(&self, low: usize, high: usize) -> Bound<'py, PyList>;

    /// Sets the item at the specified index.
    ///
    /// Raises `IndexError` if the index is out of range.
    fn set_item<I>(&self, index: usize, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>;

    /// Deletes the `index`th element of self.
    ///
    /// This is equivalent to the Python statement `del self[i]`.
    fn del_item(&self, index: usize) -> PyResult<()>;

    /// Assigns the sequence `seq` to the slice of `self` from `low` to `high`.
    ///
    /// This is equivalent to the Python statement `self[low:high] = v`.
    fn set_slice(&self, low: usize, high: usize, seq: &Bound<'_, PyAny>) -> PyResult<()>;

    /// Deletes the slice from `low` to `high` from `self`.
    ///
    /// This is equivalent to the Python statement `del self[low:high]`.
    fn del_slice(&self, low: usize, high: usize) -> PyResult<()>;

    /// Appends an item to the list.
    fn append<I>(&self, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>;

    /// Inserts an item at the specified index.
    ///
    /// If `index >= self.len()`, inserts at the end.
    fn insert<I>(&self, index: usize, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>;

    /// Determines if self contains `value`.
    ///
    /// This is equivalent to the Python expression `value in self`.
    fn contains<V>(&self, value: V) -> PyResult<bool>
    where
        V: IntoPyObject<'py>;

    /// Returns the first index `i` for which `self[i] == value`.
    ///
    /// This is equivalent to the Python expression `self.index(value)`.
    fn index<V>(&self, value: V) -> PyResult<usize>
    where
        V: IntoPyObject<'py>;

    /// Returns an iterator over this list's items.
    fn iter(&self) -> BoundListIterator<'py>;

    /// Sorts the list in-place. Equivalent to the Python expression `l.sort()`.
    fn sort(&self) -> PyResult<()>;

    /// Reverses the list in-place. Equivalent to the Python expression `l.reverse()`.
    fn reverse(&self) -> PyResult<()>;

    /// Return a new tuple containing the contents of the list; equivalent to the Python expression `tuple(list)`.
    ///
    /// This method is equivalent to `self.as_sequence().to_tuple()` and faster than `PyTuple::new(py, this_list)`.
    fn to_tuple(&self) -> Bound<'py, PyTuple>;
}

impl<'py> PyListMethods<'py> for Bound<'py, PyList> {
    /// Returns the length of the list.
    fn len(&self) -> usize {
        unsafe {
            #[cfg(not(Py_LIMITED_API))]
            let size = ffi::PyList_GET_SIZE(self.as_ptr());
            #[cfg(Py_LIMITED_API)]
            let size = ffi::PyList_Size(self.as_ptr());

            // non-negative Py_ssize_t should always fit into Rust usize
            size as usize
        }
    }

    /// Checks if the list is empty.
    fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Returns `self` cast as a `PySequence`.
    fn as_sequence(&self) -> &Bound<'py, PySequence> {
        unsafe { self.downcast_unchecked() }
    }

    /// Returns `self` cast as a `PySequence`.
    fn into_sequence(self) -> Bound<'py, PySequence> {
        unsafe { self.into_any().downcast_into_unchecked() }
    }

    /// Gets the list item at the specified index.
    /// # Example
    /// ```
    /// use pyo3::{prelude::*, types::PyList};
    /// Python::with_gil(|py| {
    ///     let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
    ///     let obj = list.get_item(0);
    ///     assert_eq!(obj.unwrap().extract::<i32>().unwrap(), 2);
    /// });
    /// ```
    fn get_item(&self, index: usize) -> PyResult<Bound<'py, PyAny>> {
        unsafe {
            ffi::compat::PyList_GetItemRef(self.as_ptr(), index as Py_ssize_t)
                .assume_owned_or_err(self.py())
        }
    }

    /// Gets the list item at the specified index. Undefined behavior on bad index. Use with caution.
    ///
    /// # Safety
    ///
    /// Caller must verify that the index is within the bounds of the list.
    #[cfg(not(any(Py_LIMITED_API, Py_GIL_DISABLED)))]
    unsafe fn get_item_unchecked(&self, index: usize) -> Bound<'py, PyAny> {
        // PyList_GET_ITEM return borrowed ptr; must make owned for safety (see #890).
        ffi::PyList_GET_ITEM(self.as_ptr(), index as Py_ssize_t)
            .assume_borrowed(self.py())
            .to_owned()
    }

    /// Takes the slice `self[low:high]` and returns it as a new list.
    ///
    /// Indices must be nonnegative, and out-of-range indices are clipped to
    /// `self.len()`.
    fn get_slice(&self, low: usize, high: usize) -> Bound<'py, PyList> {
        unsafe {
            ffi::PyList_GetSlice(self.as_ptr(), get_ssize_index(low), get_ssize_index(high))
                .assume_owned(self.py())
                .downcast_into_unchecked()
        }
    }

    /// Sets the item at the specified index.
    ///
    /// Raises `IndexError` if the index is out of range.
    fn set_item<I>(&self, index: usize, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>,
    {
        fn inner(list: &Bound<'_, PyList>, index: usize, item: Bound<'_, PyAny>) -> PyResult<()> {
            err::error_on_minusone(list.py(), unsafe {
                ffi::PyList_SetItem(list.as_ptr(), get_ssize_index(index), item.into_ptr())
            })
        }

        let py = self.py();
        inner(
            self,
            index,
            item.into_pyobject(py)
                .map_err(Into::into)?
                .into_any()
                .into_bound(),
        )
    }

    /// Deletes the `index`th element of self.
    ///
    /// This is equivalent to the Python statement `del self[i]`.
    #[inline]
    fn del_item(&self, index: usize) -> PyResult<()> {
        self.as_sequence().del_item(index)
    }

    /// Assigns the sequence `seq` to the slice of `self` from `low` to `high`.
    ///
    /// This is equivalent to the Python statement `self[low:high] = v`.
    #[inline]
    fn set_slice(&self, low: usize, high: usize, seq: &Bound<'_, PyAny>) -> PyResult<()> {
        err::error_on_minusone(self.py(), unsafe {
            ffi::PyList_SetSlice(
                self.as_ptr(),
                get_ssize_index(low),
                get_ssize_index(high),
                seq.as_ptr(),
            )
        })
    }

    /// Deletes the slice from `low` to `high` from `self`.
    ///
    /// This is equivalent to the Python statement `del self[low:high]`.
    #[inline]
    fn del_slice(&self, low: usize, high: usize) -> PyResult<()> {
        self.as_sequence().del_slice(low, high)
    }

    /// Appends an item to the list.
    fn append<I>(&self, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>,
    {
        fn inner(list: &Bound<'_, PyList>, item: Borrowed<'_, '_, PyAny>) -> PyResult<()> {
            err::error_on_minusone(list.py(), unsafe {
                ffi::PyList_Append(list.as_ptr(), item.as_ptr())
            })
        }

        let py = self.py();
        inner(
            self,
            item.into_pyobject(py)
                .map_err(Into::into)?
                .into_any()
                .as_borrowed(),
        )
    }

    /// Inserts an item at the specified index.
    ///
    /// If `index >= self.len()`, inserts at the end.
    fn insert<I>(&self, index: usize, item: I) -> PyResult<()>
    where
        I: IntoPyObject<'py>,
    {
        fn inner(
            list: &Bound<'_, PyList>,
            index: usize,
            item: Borrowed<'_, '_, PyAny>,
        ) -> PyResult<()> {
            err::error_on_minusone(list.py(), unsafe {
                ffi::PyList_Insert(list.as_ptr(), get_ssize_index(index), item.as_ptr())
            })
        }

        let py = self.py();
        inner(
            self,
            index,
            item.into_pyobject(py)
                .map_err(Into::into)?
                .into_any()
                .as_borrowed(),
        )
    }

    /// Determines if self contains `value`.
    ///
    /// This is equivalent to the Python expression `value in self`.
    #[inline]
    fn contains<V>(&self, value: V) -> PyResult<bool>
    where
        V: IntoPyObject<'py>,
    {
        self.as_sequence().contains(value)
    }

    /// Returns the first index `i` for which `self[i] == value`.
    ///
    /// This is equivalent to the Python expression `self.index(value)`.
    #[inline]
    fn index<V>(&self, value: V) -> PyResult<usize>
    where
        V: IntoPyObject<'py>,
    {
        self.as_sequence().index(value)
    }

    /// Returns an iterator over this list's items.
    fn iter(&self) -> BoundListIterator<'py> {
        BoundListIterator::new(self.clone())
    }

    /// Sorts the list in-place. Equivalent to the Python expression `l.sort()`.
    fn sort(&self) -> PyResult<()> {
        err::error_on_minusone(self.py(), unsafe { ffi::PyList_Sort(self.as_ptr()) })
    }

    /// Reverses the list in-place. Equivalent to the Python expression `l.reverse()`.
    fn reverse(&self) -> PyResult<()> {
        err::error_on_minusone(self.py(), unsafe { ffi::PyList_Reverse(self.as_ptr()) })
    }

    /// Return a new tuple containing the contents of the list; equivalent to the Python expression `tuple(list)`.
    ///
    /// This method is equivalent to `self.as_sequence().to_tuple()` and faster than `PyTuple::new(py, this_list)`.
    fn to_tuple(&self) -> Bound<'py, PyTuple> {
        unsafe {
            ffi::PyList_AsTuple(self.as_ptr())
                .assume_owned(self.py())
                .downcast_into_unchecked()
        }
    }
}

/// Used by `PyList::iter()`.
pub struct BoundListIterator<'py> {
    list: Bound<'py, PyList>,
    index: usize,
    length: usize,
}

impl<'py> BoundListIterator<'py> {
    fn new(list: Bound<'py, PyList>) -> Self {
        let length: usize = list.len();
        BoundListIterator {
            list,
            index: 0,
            length,
        }
    }

    unsafe fn get_item(&self, index: usize) -> Bound<'py, PyAny> {
        #[cfg(any(Py_LIMITED_API, PyPy, Py_GIL_DISABLED))]
        let item = self.list.get_item(index).expect("list.get failed");
        #[cfg(not(any(Py_LIMITED_API, PyPy, Py_GIL_DISABLED)))]
        let item = self.list.get_item_unchecked(index);
        item
    }
}

impl<'py> Iterator for BoundListIterator<'py> {
    type Item = Bound<'py, PyAny>;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        let length = self.length.min(self.list.len());

        if self.index < length {
            let item = unsafe { self.get_item(self.index) };
            self.index += 1;
            Some(item)
        } else {
            None
        }
    }

    #[inline]
    fn size_hint(&self) -> (usize, Option<usize>) {
        let len = self.len();
        (len, Some(len))
    }
}

impl DoubleEndedIterator for BoundListIterator<'_> {
    #[inline]
    fn next_back(&mut self) -> Option<Self::Item> {
        let length = self.length.min(self.list.len());

        if self.index < length {
            let item = unsafe { self.get_item(length - 1) };
            self.length = length - 1;
            Some(item)
        } else {
            None
        }
    }
}

impl ExactSizeIterator for BoundListIterator<'_> {
    fn len(&self) -> usize {
        self.length.saturating_sub(self.index)
    }
}

impl FusedIterator for BoundListIterator<'_> {}

impl<'py> IntoIterator for Bound<'py, PyList> {
    type Item = Bound<'py, PyAny>;
    type IntoIter = BoundListIterator<'py>;

    fn into_iter(self) -> Self::IntoIter {
        BoundListIterator::new(self)
    }
}

impl<'py> IntoIterator for &Bound<'py, PyList> {
    type Item = Bound<'py, PyAny>;
    type IntoIter = BoundListIterator<'py>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[cfg(test)]
mod tests {
    use crate::types::any::PyAnyMethods;
    use crate::types::list::PyListMethods;
    use crate::types::sequence::PySequenceMethods;
    use crate::types::{PyList, PyTuple};
    use crate::{ffi, IntoPyObject, Python};

    #[test]
    fn test_new() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(7, list.get_item(3).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_len() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 2, 3, 4]).unwrap();
            assert_eq!(4, list.len());
        });
    }

    #[test]
    fn test_get_item() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(7, list.get_item(3).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_get_slice() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let slice = list.get_slice(1, 3);
            assert_eq!(2, slice.len());
            let slice = list.get_slice(1, 7);
            assert_eq!(3, slice.len());
        });
    }

    #[test]
    fn test_set_item() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let val = 42i32.into_pyobject(py).unwrap();
            let val2 = 42i32.into_pyobject(py).unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            list.set_item(0, val).unwrap();
            assert_eq!(42, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.set_item(10, val2).is_err());
        });
    }

    #[test]
    fn test_set_item_refcnt() {
        Python::with_gil(|py| {
            let obj = py.eval(ffi::c_str!("object()"), None, None).unwrap();
            let cnt;
            {
                let v = vec![2];
                let ob = v.into_pyobject(py).unwrap();
                let list = ob.downcast::<PyList>().unwrap();
                cnt = obj.get_refcnt();
                list.set_item(0, &obj).unwrap();
            }

            assert_eq!(cnt, obj.get_refcnt());
        });
    }

    #[test]
    fn test_insert() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let val = 42i32.into_pyobject(py).unwrap();
            let val2 = 43i32.into_pyobject(py).unwrap();
            assert_eq!(4, list.len());
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            list.insert(0, val).unwrap();
            list.insert(1000, val2).unwrap();
            assert_eq!(6, list.len());
            assert_eq!(42, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(2, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(43, list.get_item(5).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_insert_refcnt() {
        Python::with_gil(|py| {
            let cnt;
            let obj = py.eval(ffi::c_str!("object()"), None, None).unwrap();
            {
                let list = PyList::empty(py);
                cnt = obj.get_refcnt();
                list.insert(0, &obj).unwrap();
            }

            assert_eq!(cnt, obj.get_refcnt());
        });
    }

    #[test]
    fn test_append() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2]).unwrap();
            list.append(3).unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_append_refcnt() {
        Python::with_gil(|py| {
            let cnt;
            let obj = py.eval(ffi::c_str!("object()"), None, None).unwrap();
            {
                let list = PyList::empty(py);
                cnt = obj.get_refcnt();
                list.append(&obj).unwrap();
            }
            assert_eq!(cnt, obj.get_refcnt());
        });
    }

    #[test]
    fn test_iter() {
        Python::with_gil(|py| {
            let v = vec![2, 3, 5, 7];
            let list = PyList::new(py, &v).unwrap();
            let mut idx = 0;
            for el in list {
                assert_eq!(v[idx], el.extract::<i32>().unwrap());
                idx += 1;
            }
            assert_eq!(idx, v.len());
        });
    }

    #[test]
    fn test_iter_size_hint() {
        Python::with_gil(|py| {
            let v = vec![2, 3, 5, 7];
            let ob = (&v).into_pyobject(py).unwrap();
            let list = ob.downcast::<PyList>().unwrap();

            let mut iter = list.iter();
            assert_eq!(iter.size_hint(), (v.len(), Some(v.len())));
            iter.next();
            assert_eq!(iter.size_hint(), (v.len() - 1, Some(v.len() - 1)));

            // Exhaust iterator.
            for _ in &mut iter {}

            assert_eq!(iter.size_hint(), (0, Some(0)));
        });
    }

    #[test]
    fn test_iter_rev() {
        Python::with_gil(|py| {
            let v = vec![2, 3, 5, 7];
            let ob = v.into_pyobject(py).unwrap();
            let list = ob.downcast::<PyList>().unwrap();

            let mut iter = list.iter().rev();

            assert_eq!(iter.size_hint(), (4, Some(4)));

            assert_eq!(iter.next().unwrap().extract::<i32>().unwrap(), 7);
            assert_eq!(iter.size_hint(), (3, Some(3)));

            assert_eq!(iter.next().unwrap().extract::<i32>().unwrap(), 5);
            assert_eq!(iter.size_hint(), (2, Some(2)));

            assert_eq!(iter.next().unwrap().extract::<i32>().unwrap(), 3);
            assert_eq!(iter.size_hint(), (1, Some(1)));

            assert_eq!(iter.next().unwrap().extract::<i32>().unwrap(), 2);
            assert_eq!(iter.size_hint(), (0, Some(0)));

            assert!(iter.next().is_none());
            assert!(iter.next().is_none());
        });
    }

    #[test]
    fn test_into_iter() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 2, 3, 4]).unwrap();
            for (i, item) in list.iter().enumerate() {
                assert_eq!((i + 1) as i32, item.extract::<i32>().unwrap());
            }
        });
    }

    #[test]
    fn test_into_iter_bound() {
        use crate::types::any::PyAnyMethods;

        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 2, 3, 4]).unwrap();
            let mut items = vec![];
            for item in &list {
                items.push(item.extract::<i32>().unwrap());
            }
            assert_eq!(items, vec![1, 2, 3, 4]);
        });
    }

    #[test]
    fn test_as_sequence() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 2, 3, 4]).unwrap();

            assert_eq!(list.as_sequence().len().unwrap(), 4);
            assert_eq!(
                list.as_sequence()
                    .get_item(1)
                    .unwrap()
                    .extract::<i32>()
                    .unwrap(),
                2
            );
        });
    }

    #[test]
    fn test_into_sequence() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 2, 3, 4]).unwrap();

            let sequence = list.into_sequence();

            assert_eq!(sequence.len().unwrap(), 4);
            assert_eq!(sequence.get_item(1).unwrap().extract::<i32>().unwrap(), 2);
        });
    }

    #[test]
    fn test_extract() {
        Python::with_gil(|py| {
            let v = vec![2, 3, 5, 7];
            let list = PyList::new(py, &v).unwrap();
            let v2 = list.as_ref().extract::<Vec<i32>>().unwrap();
            assert_eq!(v, v2);
        });
    }

    #[test]
    fn test_sort() {
        Python::with_gil(|py| {
            let v = vec![7, 3, 2, 5];
            let list = PyList::new(py, &v).unwrap();
            assert_eq!(7, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(2, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(3).unwrap().extract::<i32>().unwrap());
            list.sort().unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(7, list.get_item(3).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_reverse() {
        Python::with_gil(|py| {
            let v = vec![2, 3, 5, 7];
            let list = PyList::new(py, &v).unwrap();
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(7, list.get_item(3).unwrap().extract::<i32>().unwrap());
            list.reverse().unwrap();
            assert_eq!(7, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(5, list.get_item(1).unwrap().extract::<i32>().unwrap());
            assert_eq!(3, list.get_item(2).unwrap().extract::<i32>().unwrap());
            assert_eq!(2, list.get_item(3).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_array_into_pyobject() {
        Python::with_gil(|py| {
            let array = [1, 2].into_pyobject(py).unwrap();
            let list = array.downcast::<PyList>().unwrap();
            assert_eq!(1, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert_eq!(2, list.get_item(1).unwrap().extract::<i32>().unwrap());
        });
    }

    #[test]
    fn test_list_get_item_invalid_index() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let obj = list.get_item(5);
            assert!(obj.is_err());
            assert_eq!(
                obj.unwrap_err().to_string(),
                "IndexError: list index out of range"
            );
        });
    }

    #[test]
    fn test_list_get_item_sanity() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let obj = list.get_item(0);
            assert_eq!(obj.unwrap().extract::<i32>().unwrap(), 2);
        });
    }

    #[cfg(not(any(Py_LIMITED_API, PyPy, Py_GIL_DISABLED)))]
    #[test]
    fn test_list_get_item_unchecked_sanity() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [2, 3, 5, 7]).unwrap();
            let obj = unsafe { list.get_item_unchecked(0) };
            assert_eq!(obj.extract::<i32>().unwrap(), 2);
        });
    }

    #[test]
    fn test_list_del_item() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 1, 2, 3, 5, 8]).unwrap();
            assert!(list.del_item(10).is_err());
            assert_eq!(1, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(1, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(2, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(3, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(5, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(8, list.get_item(0).unwrap().extract::<i32>().unwrap());
            assert!(list.del_item(0).is_ok());
            assert_eq!(0, list.len());
            assert!(list.del_item(0).is_err());
        });
    }

    #[test]
    fn test_list_set_slice() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 1, 2, 3, 5, 8]).unwrap();
            let ins = PyList::new(py, [7, 4]).unwrap();
            list.set_slice(1, 4, &ins).unwrap();
            assert_eq!([1, 7, 4, 5, 8], list.extract::<[i32; 5]>().unwrap());
            list.set_slice(3, 100, &PyList::empty(py)).unwrap();
            assert_eq!([1, 7, 4], list.extract::<[i32; 3]>().unwrap());
        });
    }

    #[test]
    fn test_list_del_slice() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 1, 2, 3, 5, 8]).unwrap();
            list.del_slice(1, 4).unwrap();
            assert_eq!([1, 5, 8], list.extract::<[i32; 3]>().unwrap());
            list.del_slice(1, 100).unwrap();
            assert_eq!([1], list.extract::<[i32; 1]>().unwrap());
        });
    }

    #[test]
    fn test_list_contains() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 1, 2, 3, 5, 8]).unwrap();
            assert_eq!(6, list.len());

            let bad_needle = 7i32.into_pyobject(py).unwrap();
            assert!(!list.contains(&bad_needle).unwrap());

            let good_needle = 8i32.into_pyobject(py).unwrap();
            assert!(list.contains(&good_needle).unwrap());

            let type_coerced_needle = 8f32.into_pyobject(py).unwrap();
            assert!(list.contains(&type_coerced_needle).unwrap());
        });
    }

    #[test]
    fn test_list_index() {
        Python::with_gil(|py| {
            let list = PyList::new(py, [1, 1, 2, 3, 5, 8]).unwrap();
            assert_eq!(0, list.index(1i32).unwrap());
            assert_eq!(2, list.index(2i32).unwrap());
            assert_eq!(3, list.index(3i32).unwrap());
            assert_eq!(4, list.index(5i32).unwrap());
            assert_eq!(5, list.index(8i32).unwrap());
            assert!(list.index(42i32).is_err());
        });
    }

    use std::ops::Range;

    // An iterator that lies about its `ExactSizeIterator` implementation.
    // See https://github.com/PyO3/pyo3/issues/2118
    struct FaultyIter(Range<usize>, usize);

    impl Iterator for FaultyIter {
        type Item = usize;

        fn next(&mut self) -> Option<Self::Item> {
            self.0.next()
        }
    }

    impl ExactSizeIterator for FaultyIter {
        fn len(&self) -> usize {
            self.1
        }
    }

    #[test]
    #[should_panic(
        expected = "Attempted to create PyList but `elements` was larger than reported by its `ExactSizeIterator` implementation."
    )]
    fn too_long_iterator() {
        Python::with_gil(|py| {
            let iter = FaultyIter(0..usize::MAX, 73);
            let _list = PyList::new(py, iter).unwrap();
        })
    }

    #[test]
    #[should_panic(
        expected = "Attempted to create PyList but `elements` was smaller than reported by its `ExactSizeIterator` implementation."
    )]
    fn too_short_iterator() {
        Python::with_gil(|py| {
            let iter = FaultyIter(0..35, 73);
            let _list = PyList::new(py, iter).unwrap();
        })
    }

    #[test]
    #[should_panic(
        expected = "out of range integral type conversion attempted on `elements.len()`"
    )]
    fn overflowing_size() {
        Python::with_gil(|py| {
            let iter = FaultyIter(0..0, usize::MAX);

            let _list = PyList::new(py, iter).unwrap();
        })
    }

    #[test]
    fn bad_intopyobject_doesnt_cause_leaks() {
        use crate::types::PyInt;
        use std::convert::Infallible;
        use std::sync::atomic::{AtomicUsize, Ordering::SeqCst};
        static NEEDS_DESTRUCTING_COUNT: AtomicUsize = AtomicUsize::new(0);

        struct Bad(usize);

        impl Drop for Bad {
            fn drop(&mut self) {
                NEEDS_DESTRUCTING_COUNT.fetch_sub(1, SeqCst);
            }
        }

        impl<'py> IntoPyObject<'py> for Bad {
            type Target = PyInt;
            type Output = crate::Bound<'py, Self::Target>;
            type Error = Infallible;

            fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
                // This panic should not lead to a memory leak
                assert_ne!(self.0, 42);
                self.0.into_pyobject(py)
            }
        }

        struct FaultyIter(Range<usize>, usize);

        impl Iterator for FaultyIter {
            type Item = Bad;

            fn next(&mut self) -> Option<Self::Item> {
                self.0.next().map(|i| {
                    NEEDS_DESTRUCTING_COUNT.fetch_add(1, SeqCst);
                    Bad(i)
                })
            }
        }

        impl ExactSizeIterator for FaultyIter {
            fn len(&self) -> usize {
                self.1
            }
        }

        Python::with_gil(|py| {
            std::panic::catch_unwind(|| {
                let iter = FaultyIter(0..50, 50);
                let _list = PyList::new(py, iter).unwrap();
            })
            .unwrap_err();
        });

        assert_eq!(
            NEEDS_DESTRUCTING_COUNT.load(SeqCst),
            0,
            "Some destructors did not run"
        );
    }

    #[test]
    fn test_list_to_tuple() {
        Python::with_gil(|py| {
            let list = PyList::new(py, vec![1, 2, 3]).unwrap();
            let tuple = list.to_tuple();
            let tuple_expected = PyTuple::new(py, vec![1, 2, 3]).unwrap();
            assert!(tuple.eq(tuple_expected).unwrap());
        })
    }
}
