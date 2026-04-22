import { ALIGNMENT, COLOR } from './common.js';
import { Valuetransform } from './external-table.js';

/*
All the fields of Internal Table has to be mandatory
These fields are generated based on user input
and during generated is some input is missing it is filled by default value.
*/

export interface Column {
  name: string;
  title: string;
  alignment?: ALIGNMENT;
  color?: COLOR;
  length?: number;
  minLen?: number;
  maxLen?: number;
  transform?: Valuetransform;
}

type TableLineDetailsKeys = 'left' | 'right' | 'mid' | 'other';

export type TableLineDetails = {
  [key in TableLineDetailsKeys]: string;
};

export type TableStyleDetails = {
  headerTop: TableLineDetails;
  headerBottom: TableLineDetails;
  tableBottom: TableLineDetails;
  vertical: string;
  rowSeparator: TableLineDetails;
};
