// Package version holds build-time metadata injected via -ldflags.
package version

var (
	// Version is the project release version (e.g. "1.0.0").
	Version = "dev"
	// GitCommit is the short git SHA embedded at build time.
	GitCommit = "unknown"
	// BuildDate is the RFC-3339 timestamp embedded at build time.
	BuildDate = "unknown"
)
