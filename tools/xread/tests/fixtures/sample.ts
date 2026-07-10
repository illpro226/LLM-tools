// Sample TypeScript module for xread tests.

import { EventEmitter } from "events";

export interface Greetable {
  name: string;
  greet(): string;
}

export type Language = "en" | "es";

// Format a name for display.
export function formatName(first: string, last: string): string {
  return `${first} ${last}`;
}

export const shout = (text: string): string => {
  return text.toUpperCase() + "!";
};

export class Greeter extends EventEmitter {
  private language: Language;

  constructor(language: Language = "en") {
    super();
    this.language = language;
  }

  // The main entry point for greetings.
  greet(target: Greetable): string {
    if (this.language === "en") {
      return `hello, ${target.name}`;
    }
    return `hola, ${target.name}`;
  }

  static default(): Greeter {
    return new Greeter();
  }
}

export default function farewell(name: string): string {
  return `bye, ${name}`;
}
