package ipc

import (
	"bufio"
	"bytes"
	"strings"
	"testing"
)

func TestReadMessage_basic(t *testing.T) {
	msg := `{"type":"hello"}` + "\n"
	r := bufio.NewReader(strings.NewReader(msg))
	got, err := ReadMessage(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !bytes.Equal(got, []byte(msg)) {
		t.Fatalf("got %q want %q", got, msg)
	}
}

func TestReadMessage_multipleMessages(t *testing.T) {
	input := `{"type":"hello"}` + "\n" + `{"type":"heartbeat"}` + "\n"
	r := bufio.NewReader(strings.NewReader(input))

	m1, err := ReadMessage(r)
	if err != nil {
		t.Fatalf("first read: %v", err)
	}
	if string(m1) != `{"type":"hello"}`+"\n" {
		t.Fatalf("first msg got %q", m1)
	}

	m2, err := ReadMessage(r)
	if err != nil {
		t.Fatalf("second read: %v", err)
	}
	if string(m2) != `{"type":"heartbeat"}`+"\n" {
		t.Fatalf("second msg got %q", m2)
	}
}

func TestReadMessage_oversized(t *testing.T) {
	// Build a line that exceeds MaxMessageBytes.
	big := make([]byte, MaxMessageBytes+10)
	for i := range big {
		big[i] = 'x'
	}
	big[len(big)-1] = '\n'

	r := bufio.NewReaderSize(bytes.NewReader(big), len(big)+1)
	_, err := ReadMessage(r)
	if err == nil {
		t.Fatal("expected error for oversized message, got nil")
	}
}

func TestWriteMessage_basic(t *testing.T) {
	var buf bytes.Buffer
	data := []byte(`{"type":"hello"}`)
	if err := WriteMessage(&buf, data); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := append(data, '\n')
	if !bytes.Equal(buf.Bytes(), want) {
		t.Fatalf("got %q want %q", buf.Bytes(), want)
	}
}

func TestWriteMessage_oversized(t *testing.T) {
	big := make([]byte, MaxMessageBytes)
	var buf bytes.Buffer
	err := WriteMessage(&buf, big)
	if err == nil {
		t.Fatal("expected error for oversized outgoing message")
	}
}

func TestRoundTrip(t *testing.T) {
	original := []byte(`{"type":"tool_call","request_id":"abc","tool_name":"get_texture_info"}`)
	var buf bytes.Buffer
	if err := WriteMessage(&buf, original); err != nil {
		t.Fatalf("write: %v", err)
	}
	r := bufio.NewReader(&buf)
	got, err := ReadMessage(r)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	// Written message includes the trailing newline.
	want := append(original, '\n')
	if !bytes.Equal(got, want) {
		t.Fatalf("roundtrip mismatch: got %q want %q", got, want)
	}
}
