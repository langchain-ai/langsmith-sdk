package transport

// CursorPage tracks cursor-based pagination state.
type CursorPage struct {
	NextCursor string
}

// HasNext reports whether a next cursor is available.
func (p CursorPage) HasNext() bool {
	return p.NextCursor != ""
}

// OffsetPage tracks offset-based pagination state.
type OffsetPage struct {
	Offset int
	Limit  int
}

// Advance moves the offset forward by n items.
func (p *OffsetPage) Advance(n int) {
	if n < 0 {
		return
	}
	p.Offset += n
}
