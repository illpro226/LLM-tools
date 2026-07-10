/// A point in 2-D space.
pub struct Point {
    pub x: f64,
    pub y: f64,
}

impl Point {
    pub fn origin() -> Point {
        Point { x: 0.0, y: 0.0 }
    }
}

/// Common shape behaviour.
pub trait Shape {
    fn area(&self) -> f64;
}

/// Sums two numbers.
pub fn combine(a: i32, b: i32) -> i32 {
    a + b
}
