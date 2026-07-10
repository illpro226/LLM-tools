package integration

import (
	"testing"

	"fixture/mathutil"
)

func TestIntegration(t *testing.T) {
	if mathutil.Add(1, 1) != 2 {
		t.Fatal("bad")
	}
}
