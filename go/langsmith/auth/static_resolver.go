package auth

import "context"

// StaticResolver always returns the same credentials.
type StaticResolver struct {
	creds Credentials
}

// NewStaticResolver creates a resolver with fixed credentials.
func NewStaticResolver(creds Credentials) *StaticResolver {
	return &StaticResolver{creds: creds}
}

// Resolve returns the resolver's fixed credentials.
func (r *StaticResolver) Resolve(_ context.Context) (Credentials, error) {
	return r.creds, nil
}
