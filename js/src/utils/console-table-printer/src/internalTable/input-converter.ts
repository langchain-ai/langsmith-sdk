import { ALIGNMENT, COLOR } from '../models/common.js';
import {
  ColumnOptionsRaw,
  ComputedColumn,
  DefaultColumnOptions,
} from '../models/external-table.js';
import { Column } from '../models/internal-table.js';
import { DEFAULT_ROW_ALIGNMENT } from '../utils/table-constants.js';

export const objIfExists = (key: string, val: any) => {
  if (!val) {
    return {};
  }

  return {
    [key]: val,
  };
};

export const rawColumnToInternalColumn = (
  column: ColumnOptionsRaw | ComputedColumn,
  defaultColumnStyles?: DefaultColumnOptions
): Column => ({
  name: column.name,
  title: column.title ?? column.name,
  ...objIfExists(
    'color',
    (column.color || defaultColumnStyles?.color) as COLOR
  ),
  ...objIfExists(
    'maxLen',
    (column.maxLen || defaultColumnStyles?.maxLen) as number
  ),
  ...objIfExists(
    'minLen',
    (column.minLen || defaultColumnStyles?.minLen) as number
  ),
  alignment: (column.alignment ||
    defaultColumnStyles?.alignment ||
    DEFAULT_ROW_ALIGNMENT) as ALIGNMENT,
  transform: column.transform,
});
