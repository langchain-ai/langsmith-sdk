package transport

import (
	"net/http"
	"net/url"
)

// Request is a transport-level request envelope.
type Request struct {
	Method  string
	Path    string
	Query   url.Values
	Headers http.Header
	Body    any
}

// Response is a transport-level response envelope.
type Response struct {
	StatusCode int
	Headers    http.Header
	Body       []byte
}
