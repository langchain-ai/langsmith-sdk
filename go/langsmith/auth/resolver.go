package auth

import "context"

// Resolver provides credentials for outgoing requests.
type Resolver interface {
	Resolve(ctx context.Context) (Credentials, error)
}
