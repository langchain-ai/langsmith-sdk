import { CharLengthDict, COLOR, Dictionary, Row } from '../models/common.js';
import { CellValue, Valuetransform } from '../models/external-table.js';
import { Column, TableLineDetails } from '../models/internal-table.js';
import { findWidthInConsole } from './console-utils.js';
import {
  biggestWordInSentence,
  splitTextIntoTextsOfMinLen,
} from './string-utils.js';
import {
  DEFAULT_COLUMN_LEN,
  DEFAULT_HEADER_FONT_COLOR,
  DEFAULT_ROW_SEPARATOR,
} from './table-constants.js';

const max = (a: number, b: number) => Math.max(a, b);

// takes any input that is given by user and converts to string
export const cellText = (text: CellValue): string =>
  text === undefined || text === null ? '' : `${text}`;

// evaluate cell text with defined transform
export const evaluateCellText = (
  text: CellValue,
  transform?: Valuetransform
): string => (transform ? `${transform(text)}` : cellText(text));

export interface RowOptionsRaw {
  color?: string;
  separator?: boolean;
}

export interface RowOptions {
  color: COLOR;
  separator: boolean;
}

export interface CreateRowFunction {
  (color: COLOR, text: Dictionary, separator: boolean): Row;
}

export const convertRawRowOptionsToStandard = (
  options?: RowOptionsRaw
): RowOptions | undefined => {
  if (options) {
    return {
      color: options.color as COLOR,
      separator: options.separator || DEFAULT_ROW_SEPARATOR,
    };
  }
  return undefined;
};

// ({ left: "╚", mid: "╩", right: "╝", other: "═" }, [5, 10, 7]) => "╚═══════╩════════════╩═════════╝"
export const createTableHorizontalBorders = (
  { left, mid, right, other }: TableLineDetails,
  column_lengths: number[]
) => {
  // ╚
  let ret = left;

  // ╚═══════╩═══════════════════════════════════════╩════════╩
  column_lengths.forEach((len) => {
    ret += other.repeat(len + 2);
    ret += mid;
  });

  // ╚═══════╩═══════════════════════════════════════╩════════
  ret = ret.slice(0, -mid.length);

  // ╚═══════╩═══════════════════════════════════════╩════════╝
  ret += right;
  return ret;
};

// ("id") => { name: "id", title: "id" }
export const createColumFromOnlyName = (
  name: string
): { name: string; title: string } => ({
  name,
  title: name,
});

// ("green", { id: 1, name: "John" }, true) => { color: "green", separator: true, text: { id: 1, name: "John" } }
export const createRow: CreateRowFunction = (
  color: COLOR,
  text: Dictionary,
  separator: boolean
): Row => ({
  color,
  separator,
  text,
});

// ({ name: "id", title: "ID", minLen: 2 }, [{ text: { id: 1 } }, { text: { id: 100 } }]) => 3
// Calculates optimal column width based on content and constraints
export const findLenOfColumn = (
  column: Column,
  rows: Row[],
  charLength?: CharLengthDict
): number => {
  const columnId = column.name;
  const columnTitle = column.title;
  const datatransform = column.transform;
  let length = max(0, column?.minLen || 0);

  if (column.maxLen) {
    // if customer input is mentioned a max width, lets see if all other can fit here
    // if others cant fit find the max word length so that at least the table can be printed
    length = max(
      length,
      max(column.maxLen, biggestWordInSentence(columnTitle, charLength))
    );
    length = rows.reduce(
      (acc, row) =>
        max(
          acc,
          biggestWordInSentence(
            evaluateCellText(row.text[columnId], datatransform),
            charLength
          )
        ),
      length
    );
    return length;
  }

  length = max(length, findWidthInConsole(columnTitle, charLength));

  rows.forEach((row) => {
    length = max(
      length,
      findWidthInConsole(
        evaluateCellText(row.text[columnId], datatransform),
        charLength
      )
    );
  });

  return length;
};

// ({ left: "╚", mid: "╩", right: "╝", other: "═" }, [5, 10, 7]) => "╚═══════╩════════════╩═════════╝"
// (undefined, [5, 10, 7]) => ""
export const renderTableHorizontalBorders = (
  style: TableLineDetails,
  column_lengths: number[]
): string => {
  const str = createTableHorizontalBorders(style, column_lengths);
  return str;
};

// (createRow, [{ name: "id", title: "ID" }, { name: "name", title: "Name" }]) =>
// { color: "white_bold", separator: false, text: { id: "ID", name: "Name" } }
export const createHeaderAsRow = (
  createRowFn: CreateRowFunction,
  columns: Column[]
): Row => {
  const headerColor: COLOR = DEFAULT_HEADER_FONT_COLOR;
  const row: Row = createRowFn(headerColor, {}, false);
  columns.forEach((column) => {
    row.text[column.name] = column.title;
  });
  return row;
};

// ([{ name: "desc", length: 10 }], { text: { desc: "This is a long description" } })
// => { desc: ["This is a", "long", "description"] }
export const getWidthLimitedColumnsArray = (
  columns: Column[],
  row: Row,
  charLength?: CharLengthDict
): { [key: string]: string[] } => {
  const ret: { [key: string]: string[] } = {};

  columns.forEach((column) => {
    ret[column.name] = splitTextIntoTextsOfMinLen(
      cellText(row.text[column.name]),
      column.length || DEFAULT_COLUMN_LEN,
      charLength
    );
  });

  return ret;
};
