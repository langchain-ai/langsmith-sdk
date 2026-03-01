package langsmith

import (
	"context"
	"time"

	"github.com/vishnu-ssuresh/langsmith-sdk/go/langsmith/auth"
	"github.com/vishnu-ssuresh/langsmith-sdk/go/langsmith/transport"
)

const defaultEndpoint = "https://api.smith.langchain.com"

// ClientOptions configures the top-level SDK client.
type ClientOptions struct {
	APIKey      string
	Endpoint    string
	WorkspaceID string
	Timeout     time.Duration
	RetryMax    int
	UserAgent   string
}

// Client is the top-level SDK client.
type Client struct {
	transport *transport.Client
}

// NewClient wires auth and transport with safe defaults.
func NewClient(opts ClientOptions) (*Client, error) {
	endpoint := opts.Endpoint
	if endpoint == "" {
		endpoint = defaultEndpoint
	}

	retry := transport.DefaultRetryPolicy()
	if opts.RetryMax > 0 {
		retry.MaxAttempts = opts.RetryMax
	}

	resolver := auth.NewStaticResolver(auth.Credentials{
		APIKey:      opts.APIKey,
		WorkspaceID: opts.WorkspaceID,
		Endpoint:    endpoint,
	})

	t, err := transport.NewClient(transport.Options{
		BaseURL:     endpoint,
		Resolver:    resolver,
		Timeout:     opts.Timeout,
		RetryPolicy: retry,
		UserAgent:   opts.UserAgent,
	})
	if err != nil {
		return nil, err
	}

	return &Client{transport: t}, nil
}

// Do forwards a request through the shared transport client.
func (c *Client) Do(ctx context.Context, req transport.Request) (transport.Response, error) {
	return c.transport.Do(ctx, req)
}
