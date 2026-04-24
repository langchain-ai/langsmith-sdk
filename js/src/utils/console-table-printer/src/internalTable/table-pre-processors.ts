import { Row } from '../models/common.js';
import { ComputedColumn } from '../models/external-table.js';
import { Column } from '../models/internal-table.js';
import { findLenOfColumn } from '../utils/table-helpers.js';
import TableInternal from './internal-table.js';

// All these functions are ran when renderTable/printTable is called
const createComputedColumnsIfNecessary = (table: TableInternal) => {
  if (table.computedColumns.length) {
    table.computedColumns.forEach((computedColumn: ComputedColumn) => {
      // This can happen if renderTable/printTable is called multiple times
      const isColumnAlreadyExists = table.columns.some(
        (col: Column) => col.name === computedColumn.name
      );
      if (isColumnAlreadyExists) {
        return;
      }
      table.addColumn({
        ...computedColumn,
        ...table.defaultColumnOptions,
      });
      table.rows.forEach((row: Row, index: number, rowsArray: Row[]) => {
        const arrayRowText = rowsArray.map(
          (elemInRowsArray) => elemInRowsArray.text
        );
        row.text[computedColumn.name] = computedColumn.function(
          row.text,
          index,
          arrayRowText
        );
      });
    });
  }
};

const disableColumnsIfNecessary = (table: TableInternal) => {
  if (table.enabledColumns.length) {
    table.columns = table.columns.filter((col: Column) =>
      table.enabledColumns.includes(col.name)
    );
  }
};

const enableColumnsIfNecessary = (table: TableInternal) => {
  if (table.disabledColumns.length) {
    table.columns = table.columns.filter(
      (col: Column) => !table.disabledColumns.includes(col.name)
    );
  }
};

const findColumnWidth = (table: TableInternal) => {
  table.columns.forEach((column) => {
    column.length = findLenOfColumn(column, table.rows, table.charLength);
  });
};

export const preProcessColumns = (table: TableInternal) => {
  createComputedColumnsIfNecessary(table);
  enableColumnsIfNecessary(table);
  disableColumnsIfNecessary(table);
  findColumnWidth(table);
};

export const preProcessRows = (table: TableInternal) => {
  const newRows = table.rows
    .filter((r) => table.filterFunction(r.text))
    .sort((r1, r2) => table.sortFunction(r1.text, r2.text));
  table.rows = newRows;
};
