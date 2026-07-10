import { add } from './mathutil.js';
import { Rectangle, Square as Sq } from './shapes';

export function buildShapes() {
  const r = new Rectangle(2, 3);
  const s = new Sq(3);
  return add(r.area(), s.area());
}
