package transport

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/vishnu-ssuresh/langsmith-sdk/go/langsmith/auth"
)

// Options configures the shared transport client.
type Options struct {
	BaseURL     string
	Resolver    auth.Resolver
	Timeout     time.Duration
	RetryPolicy RetryPolicy
	UserAgent   string
	HTTPClient  *http.Client
}

// Client owns shared HTTP behavior for LangSmith requests.
type Client struct {
	baseURL    *url.URL
	resolver   auth.Resolver
	httpClient *http.Client
	retry      RetryPolicy
	userAgent  string
}

// NewClient validates options and returns a transport client.
func NewClient(opts Options) (*Client, error) {
	if opts.BaseURL == "" {
		return nil, fmt.Errorf("transport: base URL is required")
	}
	if opts.Resolver == nil {
		return nil, fmt.Errorf("transport: resolver is required")
	}

	baseURL, err := url.Parse(strings.TrimRight(opts.BaseURL, "/"))
	if err != nil {
		return nil, fmt.Errorf("transport: parse base URL: %w", err)
	}

	httpClient := opts.HTTPClient
	if httpClient == nil {
		timeout := opts.Timeout
		if timeout <= 0 {
			timeout = 30 * time.Second
		}
		httpClient = &http.Client{Timeout: timeout}
	}

	retry := opts.RetryPolicy
	if retry.MaxAttempts == 0 && retry.BaseBackoff == 0 && retry.MaxBackoff == 0 && retry.Jitter == 0 {
		retry = DefaultRetryPolicy()
	}

	return &Client{
		baseURL:    baseURL,
		resolver:   opts.Resolver,
		httpClient: httpClient,
		retry:      retry,
		userAgent:  opts.UserAgent,
	}, nil
}

// Do is a placeholder until request execution is implemented.
func (c *Client) Do(_ context.Context, _ Request) (Response, error) {
	return Response{}, fmt.Errorf("transport: Do not implemented yet")
}
