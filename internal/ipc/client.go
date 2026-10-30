package ipc

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
)

// Client is a simple synchronous IPC client for the RenderEyeMCP service.
type Client struct {
	conn   net.Conn
	reader *bufio.Reader
	writer *bufio.Writer
}

// NewClient dials a TCP connection to the given host and port.
func NewClient(host string, port int) (*Client, error) {
	addr := net.JoinHostPort(host, fmt.Sprintf("%d", port))
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("dial %s: %w", addr, err)
	}
	return &Client{
		conn:   conn,
		reader: bufio.NewReaderSize(conn, 64*1024),
		writer: bufio.NewWriterSize(conn, 64*1024),
	}, nil
}

// Send marshals msg to compact JSON and writes it as a framed message.
func (c *Client) Send(msg interface{}) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	if err := WriteMessage(c.writer, data); err != nil {
		return fmt.Errorf("write message: %w", err)
	}
	return c.writer.Flush()
}

// Receive reads the next framed message and returns the raw JSON bytes.
func (c *Client) Receive() ([]byte, error) {
	line, err := ReadMessage(c.reader)
	if err != nil {
		return nil, fmt.Errorf("read message: %w", err)
	}
	return line, nil
}

// ReceiveAs reads the next message and unmarshals it into target.
func (c *Client) ReceiveAs(target interface{}) error {
	data, err := c.Receive()
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, target); err != nil {
		return fmt.Errorf("unmarshal: %w", err)
	}
	return nil
}

// Close closes the underlying TCP connection.
func (c *Client) Close() error {
	return c.conn.Close()
}
