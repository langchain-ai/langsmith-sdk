import mk_wcwidth from './wcwidth.js';

const mk_wcswidth = (pwcs: string) => {
  let width = 0;

  // eslint-disable-next-line no-plusplus
  for (let i = 0; i < pwcs.length; i++) {
    const charCode = pwcs.charCodeAt(i);
    const w = mk_wcwidth(charCode);
    if (w < 0) {
      return -1;
    }
    width += w;
  }

  return width;
};

export default mk_wcswidth;
