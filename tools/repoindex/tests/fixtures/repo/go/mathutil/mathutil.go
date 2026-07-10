// Package mathutil provides small math helpers.
package mathutil

// Add returns the sum of two ints.
func Add(a, b int) int {
	return a + b
}

// privateHelper is unexported.
func privateHelper(x, factor int) int {
	return x * factor
}
