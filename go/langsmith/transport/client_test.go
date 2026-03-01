package transport

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/url"
	"reflect"
	"strings"
	"testing"

	"github.com/vishnu-ssuresh/langsmith-sdk/go/langsmith/auth"
)

type errResolver struct {
	err error
}

func (r errResolver) Resolve(context.Context) (auth.Credentials, error) {
	return auth.Credentials{}, r.err
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func TestDo_ValidatesRequiredFields(t *testing.T) {
	t.Parallel()

	client, err := NewClient(Options{
		BaseURL:  "http://example.com",
		Resolver: auth.NewStaticResolver(auth.Credentials{APIKey: "test-key"}),
	})
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	tests := []struct {
		name    string
		req     Request
		wantErr string
	}{
		{
			name:    "missing method",
			req:     Request{Path: "/runs"},
			wantErr: "method is required",
		},
		{
			name:    "missing path",
			req:     Request{Method: http.MethodGet},
			wantErr: "path is required",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			_, err := client.Do(context.Background(), tt.req)
			if err == nil || !strings.Contains(err.Error(), tt.wantErr) {
				t.Fatalf("Do() error = %v, want containing %q", err, tt.wantErr)
			}
		})
	}
}

func TestDo_SendsHeadersQueryAndBody(t *testing.T) {
	t.Parallel()

	httpClient := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			if r.Method != http.MethodPost {
				t.Fatalf("method = %s, want POST", r.Method)
			}
			if r.URL.Path != "/runs" {
				t.Fatalf("path = %s, want /runs", r.URL.Path)
			}
			if got := r.URL.Query()["tag"]; !reflect.DeepEqual(got, []string{"a", "b"}) {
				t.Fatalf("query tag = %v, want [a b]", got)
			}
			if got := r.Header.Get("X-API-Key"); got != "api-key-123" {
				t.Fatalf("X-API-Key = %q, want %q", got, "api-key-123")
			}
			if got := r.Header.Get("X-Tenant-Id"); got != "workspace-1" {
				t.Fatalf("X-Tenant-Id = %q, want %q", got, "workspace-1")
			}
			if got := r.Header.Get("User-Agent"); got != "fetch-go-test" {
				t.Fatalf("User-Agent = %q, want %q", got, "fetch-go-test")
			}
			if got := r.Header.Get("Content-Type"); !strings.Contains(got, "application/json") {
				t.Fatalf("Content-Type = %q, want application/json", got)
			}

			body, err := io.ReadAll(r.Body)
			if err != nil {
				t.Fatalf("ReadAll() error = %v", err)
			}
			defer r.Body.Close()
			if !strings.Contains(string(body), `"name":"demo"`) {
				t.Fatalf("request body = %s, want JSON containing name=demo", string(body))
			}

			return &http.Response{
				StatusCode: http.StatusCreated,
				Header:     http.Header{"X-Test": []string{"ok"}},
				Body:       io.NopCloser(strings.NewReader(`{"ok":true}`)),
			}, nil
		}),
	}

	client, err := NewClient(Options{
		BaseURL: "https://api.smith.langchain.com",
		Resolver: auth.NewStaticResolver(auth.Credentials{
			APIKey:      "api-key-123",
			WorkspaceID: "workspace-1",
		}),
		UserAgent:  "fetch-go-test",
		HTTPClient: httpClient,
	})
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	resp, err := client.Do(context.Background(), Request{
		Method: http.MethodPost,
		Path:   "/runs",
		Query: url.Values{
			"tag": {"a", "b"},
		},
		Body: map[string]string{"name": "demo"},
	})
	if err != nil {
		t.Fatalf("Do() error = %v", err)
	}
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusCreated)
	}
	if got := resp.Headers.Get("X-Test"); got != "ok" {
		t.Fatalf("response header X-Test = %q, want %q", got, "ok")
	}
	if got := string(resp.Body); got != `{"ok":true}` {
		t.Fatalf("response body = %q, want %q", got, `{"ok":true}`)
	}
}

func TestDo_ResolverError(t *testing.T) {
	t.Parallel()

	wantErr := errors.New("resolver failed")
	client, err := NewClient(Options{
		BaseURL:  "http://example.com",
		Resolver: errResolver{err: wantErr},
	})
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	_, err = client.Do(context.Background(), Request{
		Method: http.MethodGet,
		Path:   "/runs",
	})
	if err == nil || !strings.Contains(err.Error(), "resolve credentials") {
		t.Fatalf("Do() error = %v, want resolve credentials error", err)
	}
}

func TestDo_RetriesOnRetryableStatus(t *testing.T) {
	t.Parallel()

	attempts := 0
	httpClient := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			attempts++
			if attempts == 1 {
				return &http.Response{
					StatusCode: http.StatusServiceUnavailable,
					Header:     make(http.Header),
					Body:       io.NopCloser(strings.NewReader(`{"ok":false}`)),
				}, nil
			}
			return &http.Response{
				StatusCode: http.StatusOK,
				Header:     make(http.Header),
				Body:       io.NopCloser(strings.NewReader(`{"ok":true}`)),
			}, nil
		}),
	}

	client, err := NewClient(Options{
		BaseURL: "https://api.smith.langchain.com",
		Resolver: auth.NewStaticResolver(auth.Credentials{
			APIKey: "api-key-123",
		}),
		HTTPClient: httpClient,
		RetryPolicy: RetryPolicy{
			MaxAttempts: 2,
		},
	})
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	resp, err := client.Do(context.Background(), Request{
		Method: http.MethodGet,
		Path:   "/runs",
	})
	if err != nil {
		t.Fatalf("Do() error = %v", err)
	}
	if attempts != 2 {
		t.Fatalf("attempts = %d, want 2", attempts)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusOK)
	}
}

func TestDo_DoesNotRetryOnClientStatus(t *testing.T) {
	t.Parallel()

	attempts := 0
	httpClient := &http.Client{
		Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			attempts++
			return &http.Response{
				StatusCode: http.StatusBadRequest,
				Header:     make(http.Header),
				Body:       io.NopCloser(strings.NewReader(`{"error":"bad request"}`)),
			}, nil
		}),
	}

	client, err := NewClient(Options{
		BaseURL: "https://api.smith.langchain.com",
		Resolver: auth.NewStaticResolver(auth.Credentials{
			APIKey: "api-key-123",
		}),
		HTTPClient: httpClient,
		RetryPolicy: RetryPolicy{
			MaxAttempts: 3,
		},
	})
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}

	resp, err := client.Do(context.Background(), Request{
		Method: http.MethodGet,
		Path:   "/runs",
	})
	if err != nil {
		t.Fatalf("Do() error = %v", err)
	}
	if attempts != 1 {
		t.Fatalf("attempts = %d, want 1", attempts)
	}
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusBadRequest)
	}
}
