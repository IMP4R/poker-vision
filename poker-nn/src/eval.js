// Оценщик 7 карт. Возвращает целое: категория*16^5 + кикеры (base-16).
// Категории: 0 high, 1 pair, 2 two pair, 3 trips, 4 straight, 5 flush, 6 full house, 7 quads, 8 straight flush.
const P4 = 16 * 16 * 16 * 16;

export function eval7(cards) { // cards: Int array длины 7
  const rankCount = new Uint8Array(13);
  const suitCount = new Uint8Array(4);
  for (let i = 0; i < 7; i++) {
    const c = cards[i];
    rankCount[c >> 2]++;
    suitCount[c & 3]++;
  }
  // флеш?
  let fs = -1;
  for (let s = 0; s < 4; s++) if (suitCount[s] >= 5) { fs = s; break; }
  let flushRanks = null;
  if (fs >= 0) {
    flushRanks = [];
    for (let i = 0; i < 7; i++) {
      const c = cards[i];
      if ((c & 3) === fs) flushRanks.push(c >> 2);
    }
    flushRanks.sort((a, b) => b - a);
    const sfHi = straightHi(flushRanks, true);
    if (sfHi >= 0) return score(8, sfHi, 0, 0, 0, 0);
  }
  // группы по рангам
  const quads = [], trips = [], pairs = [], singles = [];
  for (let r = 12; r >= 0; r--) {
    const n = rankCount[r];
    if (n === 4) quads.push(r);
    else if (n === 3) trips.push(r);
    else if (n === 2) pairs.push(r);
    else if (n === 1) singles.push(r);
  }
  if (quads.length) {
    const k = bestOther(singles.concat(trips, pairs).sort((a, b) => b - a), 1, quads[0]);
    return score(7, quads[0], k, 0, 0, 0);
  }
  if (trips.length >= 2) return score(6, trips[0], trips[1], 0, 0, 0);
  if (trips.length === 1 && pairs.length >= 1) return score(6, trips[0], pairs[0], 0, 0, 0);
  if (fs >= 0) {
    return score(5, flushRanks[0], flushRanks[1], flushRanks[2], flushRanks[3], flushRanks[4]);
  }
  const allRanks = [];
  for (let r = 12; r >= 0; r--) if (rankCount[r] > 0) allRanks.push(r);
  const stHi = straightHi(allRanks, false);
  if (stHi >= 0) return score(4, stHi, 0, 0, 0, 0);
  if (trips.length === 1) {
    const ks = bestOther(singles.concat(pairs).sort((a, b) => b - a), 2, trips[0]);
    return score(3, trips[0], ks[0], ks[1], 0, 0);
  }
  if (pairs.length >= 2) {
    const k = bestOther(singles.concat(pairs.slice(2), trips).sort((a, b) => b - a), 1, -1);
    return score(2, pairs[0], pairs[1], k, 0, 0);
  }
  if (pairs.length === 1) {
    const ks = bestOther(singles, 3, pairs[0]);
    return score(1, pairs[0], ks[0], ks[1], ks[2], 0);
  }
  return score(0, singles[0], singles[1], singles[2], singles[3], singles[4]);
}

function bestOther(sortedDesc, n, exclude) {
  const out = [];
  for (const r of sortedDesc) {
    if (out.length >= n) break;
    if (r !== exclude) out.push(r);
  }
  while (out.length < n) out.push(0);
  return out;
}

// straightHi: массив рангов (любой порядок, дубликаты допустимы если uniq=true не применён — дубликаты не мешают битмаске)
function straightHi(ranks, isFlushSet) {
  let mask = 0;
  for (const r of ranks) mask |= (1 << r);
  // колесо A-5
  const wheel = (1 << 12) | 1 | 2 | 4 | 8;
  if ((mask & wheel) === wheel) return 3;
  for (let hi = 12; hi >= 4; hi--) {
    const need = (1 << hi) | (1 << (hi - 1)) | (1 << (hi - 2)) | (1 << (hi - 3)) | (1 << (hi - 4));
    if ((mask & need) === need) return hi;
  }
  return -1;
}

function score(cat, k1, k2, k3, k4, k5) {
  return ((((cat * 16 + k1) * 16 + k2) * 16 + k3) * 16 + k4) * 16 + k5;
}

export const HAND_NAMES = ['high card', 'pair', 'two pair', 'trips', 'straight', 'flush', 'full house', 'quads', 'straight flush'];
export function handName(scoreVal) { return HAND_NAMES[Math.floor(scoreVal / P4 / 16)]; }
