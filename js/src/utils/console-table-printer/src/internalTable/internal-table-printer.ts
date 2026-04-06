import { CharLengthDict, Dictionary, Row } from '../models/common.js';
import { ComplexOptions } from '../models/external-table.js';
import { Column, TableStyleDetails } from '../models/internal-table.js';
import ColoredConsoleLine, { ColorMap } from '../utils/colored-console-line.js';
import { textWithPadding } from '../utils/string-utils.js';
import {
  DEFAULT_COLUMN_LEN,
  DEFAULT_HEADER_ALIGNMENT,
  DEFAULT_HEADER_FONT_COLOR,
  DEFAULT_ROW_ALIGNMENT,
  DEFAULT_ROW_FONT_COLOR,
} from '../utils/table-constants.js';
import {
  cellText,
  createHeaderAsRow,
  createRow,
  getWidthLimitedColumnsArray,
  renderTableHorizontalBorders,
} from '../utils/table-helpers.js';
import TableInternal from './internal-table.js';
import { preProcessColumns, preProcessRows } from './table-pre-processors.js';

// ║ Index ║         ║        ║
const renderOneLine = (
  tableStyle: TableStyleDetails,
  columns: Column[],
  currentLineIndex: number,
  widthLimitedColumnsArray: { [key: string]: string[] },
  isHeader: boolean | undefined,
  row: Row,
  colorMap: ColorMap,
  charLength?: CharLengthDict
): string => {
  const line = new ColoredConsoleLine(colorMap);
  line.addCharsWithColor('', tableStyle.vertical); // dont Color the Column borders
  columns.forEach((column) => {
    const thisLineHasText =
      currentLineIndex < widthLimitedColumnsArray[column.name].length;

    const textForThisLine: string = thisLineHasText
      ? cellText(widthLimitedColumnsArray[column.name][currentLineIndex])
      : '';

    line.addCharsWithColor(DEFAULT_ROW_FONT_COLOR, ' ');
    line.addCharsWithColor(
      (isHeader && DEFAULT_HEADER_FONT_COLOR) || column.color || row.color,
      textWithPadding(
        textForThisLine,
        column.alignment || DEFAULT_ROW_ALIGNMENT,
        column.length || DEFAULT_COLUMN_LEN,
        charLength
      )
    );
    line.addCharsWithColor('', ` ${tableStyle.vertical}`); // dont Color the Column borders
  });
  return line.renderConsole();
};

// ║ Bold  ║    text ║  value ║
// ║ Index ║         ║        ║
const renderWidthLimitedLines = (
  tableStyle: TableStyleDetails,
  columns: Column[],
  row: Row,
  colorMap: ColorMap,
  isHeader?: boolean,
  charLength?: CharLengthDict
): string[] => {
  // { col1: ['How', 'Is', 'Going'], col2: ['I am', 'Tom'],  }
  const widthLimitedColumnsArray = getWidthLimitedColumnsArray(
    columns,
    row,
    charLength
  );

  const totalLines = Object.values(widthLimitedColumnsArray).reduce(
    (a, b) => Math.max(a, b.length),
    0
  );

  const ret = [];
  for (
    let currentLineIndex = 0;
    currentLineIndex < totalLines;
    currentLineIndex += 1
  ) {
    const singleLine = renderOneLine(
      tableStyle,
      columns,
      currentLineIndex,
      widthLimitedColumnsArray,
      isHeader,
      row,
      colorMap,
      charLength
    );

    ret.push(singleLine);
  }

  return ret;
};

const transformRow = (row: Row, columns: Column[]): Row => {
  const transformedRow = JSON.parse(JSON.stringify(row));
  const transforms: Dictionary = {};
  columns
    .filter((c) => {
      return !!c.transform;
    })
    .forEach((c) => {
      transforms[c.name] = c.transform;
    });
  Object.keys(transforms).forEach((t) => {
    transformedRow.text[t] = transforms[t](transformedRow.text[t]);
  });
  return transformedRow;
};

// ║ 1     ║     I would like some red wine please ║ 10.212 ║
const renderRow = (table: TableInternal, row: Row): string[] => {
  let ret: string[] = [];
  const transformedRow = transformRow(row, table.columns);
  ret = ret.concat(
    renderWidthLimitedLines(
      table.tableStyle,
      table.columns,
      transformedRow,
      table.colorMap,
      undefined,
      table.charLength
    )
  );
  return ret;
};

/*
                  The analysis Result
 ╔═══════╦═══════════════════════════════════════╦════════╗
*/
const renderTableTitle = (table: TableInternal): string[] => {
  const ret: string[] = [];

  if (table.title === undefined) {
    return ret;
  }

  const getTableWidth = () => {
    const reducer = (accumulator: number, currentValue: number) =>
      // ║ cell ║, 2 spaces + cellTextSize + one border on the left
      accumulator + currentValue + 2 + 1;
    return table.columns
      .map((m) => m.length || DEFAULT_COLUMN_LEN)
      .reduce(reducer, 1);
  };

  const titleWithPadding = textWithPadding(
    table.title as string,
    DEFAULT_HEADER_ALIGNMENT,
    getTableWidth()
  );
  const styledText = new ColoredConsoleLine(table.colorMap);
  styledText.addCharsWithColor(DEFAULT_HEADER_FONT_COLOR, titleWithPadding);
  //                  The analysis Result
  ret.push(styledText.renderConsole());
  return ret;
};

/*
 ╔═══════╦═══════════════════════════════════════╦════════╗
 ║ index ║                                  text ║  value ║
 ╟═══════╬═══════════════════════════════════════╬════════╢
*/
const renderTableHeaders = (table: TableInternal): string[] => {
  let ret: string[] = [];

  // ╔═══════╦═══════════════════════════════════════╦════════╗
  ret.push(
    renderTableHorizontalBorders(
      table.tableStyle.headerTop,
      table.columns.map((m: Column) => m.length || DEFAULT_COLUMN_LEN)
    )
  );

  // ║ index ║                                  text ║  value ║
  const row = createHeaderAsRow(createRow, table.columns);
  ret = ret.concat(
    renderWidthLimitedLines(
      table.tableStyle,
      table.columns,
      row,
      table.colorMap,
      true
    )
  );

  // ╟═══════╬═══════════════════════════════════════╬════════╢
  ret.push(
    renderTableHorizontalBorders(
      table.tableStyle.headerBottom,
      table.columns.map((m) => m.length || DEFAULT_COLUMN_LEN)
    )
  );

  return ret;
};

const renderTableEnding = (table: TableInternal): string[] => {
  const ret: string[] = [];
  // ╚═══════╩═══════════════════════════════════════╩════════╝
  ret.push(
    renderTableHorizontalBorders(
      table.tableStyle.tableBottom,
      table.columns.map((m) => m.length || DEFAULT_COLUMN_LEN)
    )
  );
  return ret;
};

const renderRowSeparator = (table: TableInternal, row: Row): string[] => {
  const ret: string[] = [];
  const lastRowIndex = table.rows.length - 1;
  const currentRowIndex = table.rows.indexOf(row);

  if (currentRowIndex !== lastRowIndex && row.separator) {
    // ╟═══════╬═══════════════════════════════════════╬════════╢
    ret.push(
      renderTableHorizontalBorders(
        table.tableStyle.rowSeparator,
        table.columns.map((m) => m.length || DEFAULT_COLUMN_LEN)
      )
    );
  }
  return ret;
};

export const renderTable = (table: TableInternal): string => {
  preProcessColumns(table); // enable / disable cols, find maxLn of each col/ computed Columns
  preProcessRows(table); // sort and filter

  const ret: string[] = [];
  renderTableTitle(table).forEach((row) => ret.push(row));

  renderTableHeaders(table).forEach((row) => ret.push(row));

  table.rows.forEach((row) => {
    renderRow(table, row).forEach((row_) => ret.push(row_));
    renderRowSeparator(table, row).forEach((row_) => ret.push(row_));
  });
  renderTableEnding(table).forEach((row) => ret.push(row));
  return ret.join('\n');
};

export const renderSimpleTable = (
  rows: Dictionary[],
  tableOptions?: ComplexOptions
) => {
  const table = new TableInternal(tableOptions);
  table.addRows(rows);
  return renderTable(table);
};

export const printSimpleTable = (
  rows: Dictionary[],
  tableOptions?: ComplexOptions
) => {
  console.log(renderSimpleTable(rows, tableOptions));
};
