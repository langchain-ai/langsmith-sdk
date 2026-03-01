package auth

// Credentials are the authentication values used for requests.
type Credentials struct {
	APIKey      string
	WorkspaceID string
	Endpoint    string
}
