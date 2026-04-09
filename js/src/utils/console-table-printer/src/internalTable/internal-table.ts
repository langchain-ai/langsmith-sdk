import { CharLengthDict, Dictionary, Row } from '../models/common.js';
import {
  ColumnOptionsRaw,
  ComplexOptions,
  ComputedColumn,
  DefaultColumnOptions,
  RowFilterFunction,
  RowSortFunction,
  Valuetransform,
} from '../models/external-table.js';
import { Column, TableStyleDetails } from '../models/internal-table.js';
import { ColorMap, DEFAULT_COLOR_MAP } from '../utils/colored-console-line.js';
import {
  DEFAULT_TABLE_STYLE,
  DEFAULT_ROW_ALIGNMENT,
  DEFAULT_ROW_FONT_COLOR,
  DEFAULT_ROW_SEPARATOR,
} from '../utils/table-constants.js';
import {
  createColumFromOnlyName,
  createRow,
  RowOptions,
} from '../utils/table-helpers.js';
import { rawColumnToInternalColumn } from './input-converter.js';
import { renderTable } from './internal-table-printer.js';

const DEFAULT_ROW_SORT_FUNC = () => 0;

const DEFAULT_ROW_FILTER_FUNC = () => true;

class TableInternal {
  title?: string;

  tableStyle: TableStyleDetails;

  columns: Column[];

  rows: Row[];

  filterFunction: RowFilterFunction;

  sortFunction: RowSortFunction;

  enabledColumns: string[];

  disabledColumns: string[];

  computedColumns: ComputedColumn[];

  rowSeparator: boolean;

  colorMap: ColorMap;

  charLength: CharLengthDict;

  defaultColumnOptions?: DefaultColumnOptions;

  transforms?: Record<string, Valuetransform>;

  initSimple(columns: string[]) {
    this.columns = columns.map((column) => ({
      name: column,
      title: column,
      alignment: DEFAULT_ROW_ALIGNMENT,
    }));
  }

  initDetailed(options: ComplexOptions) {
    this.title = options?.title || this.title;
    this.tableStyle = {
      ...this.tableStyle,
      ...options?.style,
    };
    this.sortFunction = options?.sort || this.sortFunction;
    this.filterFunction = options?.filter || this.filterFunction;
    this.enabledColumns = options?.enabledColumns || this.enabledColumns;
    this.disabledColumns = options?.disabledColumns || this.disabledColumns;
    this.computedColumns = options?.computedColumns || this.computedColumns;
    this.columns =
      options?.columns?.map((column) =>
        rawColumnToInternalColumn(column, options?.defaultColumnOptions)
      ) || this.columns;
    this.rowSeparator = options?.rowSeparator || this.rowSeparator;
    this.charLength = options?.charLength || this.charLength;
    this.defaultColumnOptions =
      options?.defaultColumnOptions || this.defaultColumnOptions;

    if (options?.shouldDisableColors) {
      this.colorMap = {};
    } else if (options?.colorMap) {
      this.colorMap = { ...this.colorMap, ...options.colorMap };
    }

    if (options.rows !== undefined) {
      this.addRows(options.rows);
    }
  }

  constructor(options?: ComplexOptions | string[]) {
    // default construction
    this.rows = [];
    this.columns = [];
    this.title = undefined;
    this.tableStyle = DEFAULT_TABLE_STYLE;
    this.filterFunction = DEFAULT_ROW_FILTER_FUNC;
    this.sortFunction = DEFAULT_ROW_SORT_FUNC;
    this.enabledColumns = [];
    this.disabledColumns = [];
    this.computedColumns = [];
    this.rowSeparator = DEFAULT_ROW_SEPARATOR;
    this.colorMap = DEFAULT_COLOR_MAP;
    this.charLength = {};
    this.defaultColumnOptions = undefined;
    this.transforms = {};

    if (options instanceof Array) {
      this.initSimple(options);
    } else if (typeof options === 'object') {
      this.initDetailed(options);
    }
  }

  createColumnFromRow(text: Dictionary) {
    const colNames = this.columns.map((col) => col.name);
    Object.keys(text).forEach((key) => {
      if (!colNames.includes(key)) {
        this.columns.push(
          rawColumnToInternalColumn(
            createColumFromOnlyName(key),
            this.defaultColumnOptions
          )
        );
      }
    });
  }

  addColumn(textOrObj: string | ComputedColumn | ColumnOptionsRaw) {
    const columnOptionsFromInput =
      typeof textOrObj === 'string'
        ? createColumFromOnlyName(textOrObj)
        : textOrObj;
    this.columns.push(
      rawColumnToInternalColumn(
        columnOptionsFromInput,
        this.defaultColumnOptions
      )
    );
  }

  addColumns(toBeInsertedColumns: string[] | ColumnOptionsRaw[]) {
    toBeInsertedColumns.forEach((toBeInsertedColumn) => {
      this.addColumn(toBeInsertedColumn);
    });
  }

  addRow(text: Dictionary, options?: RowOptions) {
    this.createColumnFromRow(text);
    this.rows.push(
      createRow(
        options?.color || DEFAULT_ROW_FONT_COLOR,
        text,
        options?.separator !== undefined
          ? options?.separator
          : this.rowSeparator
      )
    );
  }

  addRows(toBeInsertedRows: Dictionary[], options?: RowOptions) {
    toBeInsertedRows.forEach((toBeInsertedRow) => {
      this.addRow(toBeInsertedRow, options);
    });
  }

  renderTable() {
    return renderTable(this);
  }
}

export default TableInternal;
