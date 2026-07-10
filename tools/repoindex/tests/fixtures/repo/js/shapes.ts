// Interface + implementing/extending classes for the JS/TS side.
export interface Shape {
  area(): number;
}

export class Rectangle implements Shape {
  w: number;
  h: number;
  constructor(w: number, h: number) {
    this.w = w;
    this.h = h;
  }
  area(): number {
    return this.w * this.h;
  }
}

export class Square extends Rectangle {
  constructor(side: number) {
    super(side, side);
  }
}
