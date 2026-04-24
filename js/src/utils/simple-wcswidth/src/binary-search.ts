import { Interval } from './models.js';

/* auxiliary function for binary search in interval table */
const bisearch = (
  ucs: number,
  table: Interval[],
  tableSize: number
): number => {
  let min = 0;
  let mid: number;
  let max = tableSize;

  if (ucs < table[0].first || ucs > table[max].last) return 0;

  while (max >= min) {
    mid = Math.floor((min + max) / 2);
    if (ucs > table[mid].last) {
      min = mid + 1;
    } else if (ucs < table[mid].first) {
      max = mid - 1;
    } else {
      return 1;
    }
  }

  return 0;
};

export default bisearch;
