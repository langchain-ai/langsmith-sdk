import { COLOR } from '../models/common.js';

export type ColorMap = {
  [key in COLOR]?: string;
};

export const DEFAULT_COLOR_MAP: ColorMap = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  white_bold: '\x1b[01m',
  reset: '\x1b[0m',
};

export default class ColoredConsoleLine {
  text: string;

  colorMap: ColorMap;

  constructor(colorMap = DEFAULT_COLOR_MAP) {
    this.text = '';
    this.colorMap = colorMap;
  }

  addCharsWithColor(color: COLOR, text: string) {
    const colorAnsi = this.colorMap[color];
    this.text +=
      colorAnsi !== undefined
        ? `${colorAnsi}${text}${this.colorMap.reset}`
        : text;
  }

  renderConsole(): string {
    return this.text;
  }
}
