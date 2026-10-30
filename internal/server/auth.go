package server

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"log/slog"
	"os"

	"github.com/taqu/rendereye-mcp/internal/config"
)

// Auth manages the per-run shared secret that clients must present to register.
type Auth struct {
	token string
}

// NewAuth generates a fresh 32-byte random token and writes it to the token file.
// The token file path is defined by config.TokenPath().
func NewAuth() *Auth {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		// Should never happen; panic is appropriate here.
		panic("rendereye-ipc: failed to generate auth token: " + err.Error())
	}
	token := hex.EncodeToString(b)

	if err := os.WriteFile(config.TokenPath(), []byte(token), 0600); err != nil {
		// Non-fatal: clients without file access will simply fail auth.
		slog.Warn("failed to write auth token file", "path", config.TokenPath(), "err", err)
	}

	return &Auth{token: token}
}

// Validate returns true if the presented token matches (constant-time).
func (a *Auth) Validate(presented string) bool {
	return subtle.ConstantTimeCompare([]byte(a.token), []byte(presented)) == 1
}

// Cleanup removes the token file on service shutdown.
func (a *Auth) Cleanup() {
	if err := os.Remove(config.TokenPath()); err != nil && !os.IsNotExist(err) {
		slog.Warn("failed to remove token file", "path", config.TokenPath(), "err", err)
	}
}
