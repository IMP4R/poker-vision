import { eval7 } from './eval.js';
import { fullDeck, makeRng } from './cards.js';

// MC-эквити героя против numVillains со случайными руками.
// rollouts: число раздач. Возвращает { equity, win, tie }.
export function equityVsRandom(hero, board, numVillains, rollouts, rng) {
  const need = 5 - board.length;           // карты борда
  const perVillain = 2 * numVillains;
  const total = need + perVillain;

  const deck = fullDeck();
  const used = new Set([...hero, ...board]);
  const live = deck.filter(c => !used.has(c));

  let eq = 0, win = 0, tie = 0;
  const n = live.length;
  const hero7 = new Array(7);
  hero[0] !== undefined && (hero7[0] = hero[0]);
  hero7[1] = hero[1];
  for (let it = 0; it < rollouts; it++) {
    // partial Fisher-Yates: выбираем total карт
    const drawn = new Array(total);
    for (let i = 0; i < total; i++) {
      const j = i + Math.floor(rng() * (n - i));
      const tmp = live[i]; live[i] = live[j]; live[j] = tmp;
      drawn[i] = live[i];
    }
    // финальный борд
    for (let i = 0; i < need; i++) hero7[2 + i] = drawn[i];
    for (let i = 0; i < 5 - board.length; i++) { /* заполнено выше */ }
    hero7[0] = hero[0]; hero7[1] = hero[1];
    const hs = eval7(hero7);
    let best = -1, cnt = 0;
    for (let v = 0; v < numVillains; v++) {
      const off = need + v * 2;
      const v7 = [drawn[off], drawn[off + 1], hero7[2], hero7[3], hero7[4], hero7[5], hero7[6]];
      const vs = eval7(v7);
      if (vs > best) { best = vs; cnt = 1; }
      else if (vs === best) cnt++;
    }
    if (hs > best) { eq += 1; win++; }
    else if (hs === best) { eq += 1 / (cnt + 1); tie++; }
  }
  return { equity: eq / rollouts, win: win / rollouts, tie: tie / rollouts };
}
