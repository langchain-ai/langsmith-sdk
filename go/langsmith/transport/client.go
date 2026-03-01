package transport

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
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

// Do executes a single HTTP request with resolved credentials.
func (c *Client) Do(ctx context.Context, req Request) (Response, error) {
	if req.Method == "" {
		return Response{}, fmt.Errorf("transport: method is required")
	}
	if req.Path == "" {
		return Response{}, fmt.Errorf("transport: path is required")
	}

	endpoint := c.baseURL.ResolveReference(&url.URL{Path: strings.TrimPrefix(req.Path, "/")})
	if len(req.Query) > 0 {
		query := endpoint.Query()
		for key, values := range req.Query {
			for _, value := range values {
				query.Add(key, value)
			}
		}
		endpoint.RawQuery = query.Encode()
	}

	var payload []byte
	if req.Body != nil {
		encoded, err := json.Marshal(req.Body)
		if err != nil {
			return Response{}, fmt.Errorf("transport: marshal request body: %w", err)
		}
		payload = encoded
	}

	creds, err := c.resolver.Resolve(ctx)
	if err != nil {
		return Response{}, fmt.Errorf("transport: resolve credentials: %w", err)
	}

	headers := req.Headers.Clone()
	if headers == nil {
		headers = make(http.Header)
	}
	headers.Set("X-API-Key", creds.APIKey)
	if creds.WorkspaceID != "" {
		headers.Set("X-Tenant-Id", creds.WorkspaceID)
	}
	if c.userAgent != "" {
		headers.Set("User-Agent", c.userAgent)
	}
	if len(payload) > 0 {
		headers.Set("Content-Type", "application/json")
	}

	attempts := c.retry.MaxAttempts
	if attempts <= 0 {
		attempts = 1
	}

	for attempt := 1; attempt <= attempts; attempt++ {
		httpReq, err := http.NewRequestWithContext(ctx, req.Method, endpoint.String(), bytes.NewReader(payload))
		if err != nil {
			return Response{}, fmt.Errorf("transport: create request: %w", err)
		}
		httpReq.Header = headers.Clone()

		httpResp, err := c.httpClient.Do(httpReq)
		if err != nil {
			if attempt < attempts && shouldRetryError(err) {
				if waitErr := waitForRetry(ctx, c.retryDelay(attempt)); waitErr != nil {
					return Response{}, fmt.Errorf("transport: wait for retry: %w", waitErr)
				}
				continue
			}
			return Response{}, fmt.Errorf("transport: execute request: %w", err)
		}

		respBody, readErr := io.ReadAll(httpResp.Body)
		closeErr := httpResp.Body.Close()
		if readErr != nil {
			return Response{}, fmt.Errorf("transport: read response body: %w", readErr)
		}
		if closeErr != nil {
			return Response{}, fmt.Errorf("transport: close response body: %w", closeErr)
		}

		resp := Response{
			StatusCode: httpResp.StatusCode,
			Headers:    httpResp.Header.Clone(),
			Body:       respBody,
		}

		if attempt < attempts && shouldRetryStatus(resp.StatusCode) {
			if waitErr := waitForRetry(ctx, c.retryDelay(attempt)); waitErr != nil {
				return Response{}, fmt.Errorf("transport: wait for retry: %w", waitErr)
			}
			continue
		}

		return resp, nil
	}

	return Response{}, fmt.Errorf("transport: exhausted retry attempts")
}

func shouldRetryStatus(statusCode int) bool {
	switch statusCode {
	case http.StatusTooManyRequests, http.StatusInternalServerError, http.StatusBadGateway, http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return true
	default:
		return false
	}
}

func shouldRetryError(err error) bool {
	return !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded)
}

func (c *Client) retryDelay(attempt int) time.Duration {
	if c.retry.BaseBackoff <= 0 {
		return 0
	}

	delay := c.retry.BaseBackoff * time.Duration(1<<(attempt-1))
	if c.retry.MaxBackoff > 0 && delay > c.retry.MaxBackoff {
		delay = c.retry.MaxBackoff
	}
	if c.retry.Jitter > 0 {
		delay += time.Duration(rand.Int63n(int64(c.retry.Jitter) + 1))
	}
	return delay
}

func waitForRetry(ctx context.Context, delay time.Duration) error {
	if delay <= 0 {
		return nil
	}

	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
