package transport

import "time"

// RetryPolicy controls retry behavior for transient failures.
type RetryPolicy struct {
	MaxAttempts int
	BaseBackoff time.Duration
	MaxBackoff  time.Duration
	Jitter      time.Duration
}

// DefaultRetryPolicy returns conservative defaults suitable for most APIs.
func DefaultRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxAttempts: 3,
		BaseBackoff: 200 * time.Millisecond,
		MaxBackoff:  2 * time.Second,
		Jitter:      100 * time.Millisecond,
	}
}
