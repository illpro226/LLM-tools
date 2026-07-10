// Package app wires mathutil and shapes together.
package app

import (
	"fixture/mathutil"
	"fixture/shapes"
)

// BuildShapes exercises both packages.
func BuildShapes() float64 {
	r := shapes.Rectangle{W: 2, H: 3}
	s := shapes.Square{Side: 3}
	sum := mathutil.Add(int(r.Area()), int(s.Area()))
	return float64(sum)
}
