package langsmith

import "errors"

var (
	// ErrInvalidConfig means required SDK config is missing or malformed.
	ErrInvalidConfig = errors.New("langsmith: invalid config")
)
