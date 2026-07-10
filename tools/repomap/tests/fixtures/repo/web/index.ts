// mounts the app main view

/** Mount the view onto an element. */
export function mount(el: Element): void {
  new View(el).draw();
}

export class View {
  el: Element;

  draw(): void {}
}

export const handler = (ev: Event): void => {
  mount(ev.target as Element);
};
