import Table from './src/console-table-printer.js';
import {
  printSimpleTable as printTable,
  renderSimpleTable as renderTable,
} from './src/internalTable/internal-table-printer.js';

import { COLOR, ALIGNMENT } from './src/models/external-table.js';

export { Table, printTable, renderTable, COLOR, ALIGNMENT };
