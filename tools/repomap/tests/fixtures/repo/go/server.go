package server

// Config holds settings.
type Config struct {
	Addr string
}

// Load reads settings from a file.
func (c *Config) Load(path string) error {
	return nil
}

// Serve starts listening.
func Serve(addr string) error {
	return nil
}
