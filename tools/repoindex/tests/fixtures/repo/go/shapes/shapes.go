// Package shapes defines a Shape interface and structurally implementing structs.
package shapes

// Shape is the interface every shape satisfies.
type Shape interface {
	Area() float64
}

// Rectangle implements Shape structurally (no explicit declaration -- Go has none).
type Rectangle struct {
	W float64
	H float64
}

func (r Rectangle) Area() float64 {
	return r.W * r.H
}

// Square implements Shape too.
type Square struct {
	Side float64
}

func (s Square) Area() float64 {
	return s.Side * s.Side
}
