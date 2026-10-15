// Карты: ранги 2..A (0..12), масти s,h,d,c (0..3). card = rank*4 + suit
export const RANKS = '23456789TJQKA';
export const SUITS = 'shdc';

const RANK_IDX = { '2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7, 'T': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12 };

export function parseCard(str) {
  if (typeof str !== 'string' || str.length !== 2) throw new Error(`bad card: ${str}`);
  const r = RANK_IDX[str[0].toUpperCase()];
  const s = SUITS.indexOf(str[1].toLowerCase());
  if (r === undefined || s < 0) throw new Error(`bad card: ${str}`);
  return r * 4 + s;
}

export function cardStr(c) { return RANKS[(c >> 2)] + SUITS[c & 3]; }

export function parseCards(arr) { return arr.map(parseCard); }

export function fullDeck() { const d = []; for (let i = 0; i < 52; i++) d.push(i); return d; }

// Быстрое перемешивание (xorshift128 для воспроизводимости)
export function makeRng(seed) {
  let s = seed >>> 0 || 0x9e3779b9;
  return function () {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
