package ipc

import (
	"bufio"
	"fmt"
	"io"
)

// ReadMessage reads a single newline-terminated JSON message from reader.
// It enforces the MaxMessageBytes limit, returning an error if exceeded.
// bufio.Reader handles partial reads transparently.
func ReadMessage(reader *bufio.Reader) ([]byte, error) {
	line, err := reader.ReadBytes('\n')
	if err != nil {
		if err == io.EOF && len(line) > 0 {
			// Partial line before EOF — treat as error
			return nil, fmt.Errorf("unexpected EOF reading message: got %d bytes", len(line))
		}
		return nil, err
	}
	if len(line) > MaxMessageBytes {
		return nil, fmt.Errorf("incoming message size %d exceeds MaxMessageBytes (%d)", len(line), MaxMessageBytes)
	}
	return line, nil
}

// WriteMessage writes data followed by a newline to writer.
// The caller is responsible for providing valid JSON bytes without a trailing
// newline; WriteMessage appends the required '\n' delimiter.
func WriteMessage(writer io.Writer, data []byte) error {
	if len(data)+1 > MaxMessageBytes {
		return fmt.Errorf("outgoing message size %d exceeds MaxMessageBytes (%d)", len(data)+1, MaxMessageBytes)
	}
	buf := make([]byte, len(data)+1)
	copy(buf, data)
	buf[len(data)] = '\n'
	_, err := writer.Write(buf)
	return err
}
