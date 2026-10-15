import { eval7, handName } from '../src/eval.js';
import { parseCards, makeRng } from '../src/cards.js';
import { equityVsRandom } from '../src/equity.js';

let fails = 0;
function assert(cond, msg) {
  if (cond) console.log('  ok:', msg);
  else { console.error('  FAIL:', msg); fails++; }
}

// --- оценщик: порядок рук ---
const C = parseCards;
// royal flush (AsKsQsJsTs) > quads
assert(eval7(C(['As', 'Ks', 'Qs', 'Js', 'Ts', '2h', '3d'])) > eval7(C(['Ah', 'Ad', 'Ac', 'As', 'Kd', 'Ks', '2c'])), 'SF > quads');
// quads > full house
assert(eval7(C(['Ah', 'Ad', 'Ac', 'As', 'Kd', 'Ks', '2c'])) > eval7(C(['Ah', 'Ad', 'Ac', 'Ks', 'Kd', 'Qh', '2c'])), 'quads > FH');
// full house (AAAKK) > flush
assert(eval7(C(['Ah', 'Ad', 'Ac', 'Ks', 'Kd', 'Qh', '2c'])) > eval7(C(['Ah', 'Kh', 'Qh', '9h', '5h', '5d', '2c'])), 'FH > flush');
// straight A2345 (wheel) — младше стрита 23456
const wheel = eval7(C(['Ad', '2c', '3h', '4s', '5d', 'Kh', 'Qc']));
const six = eval7(C(['Ad', '2c', '3h', '4s', '6d', 'Kh', 'Qc']));
assert(wheel < six, 'wheel < 6-high straight');
assert(wheel > eval7(C(['Ah', 'Ad', 'Kc', 'Ks', 'Qd', '2h', '2c'])), 'wheel > two pair');
// straight на 7 картах с дублями
assert(eval7(C(['9h', 'Th', 'Jc', 'Qd', 'Ks', 'Kd', '2c'])) > eval7(C(['Ah', 'Ad', 'Kc', 'Ks', 'Qd', 'Jh', 'Tc'])), 'K-high straight > aces up');
// флеш vs стрит
assert(eval7(C(['2h', '5h', '9h', 'Jh', 'Kh', 'Ad', 'Ac'])) > eval7(C(['Ah', 'Ad', 'Kc', 'Ks', 'Qd', 'Jh', 'Tc'])), 'flush > straight');
// пара тузов vs пара королей
assert(eval7(C(['Ah', 'Ad', '2c', '7s', '9d', 'Jh', 'Qc'])) > eval7(C(['Kh', 'Kd', 'Ac', '7s', '9d', 'Jh', 'Qc'])), 'AA > KK');
// названия
assert(handName(eval7(C(['As', 'Ks', 'Qs', 'Js', 'Ts', '2h', '3d']))) === 'straight flush', 'name SF');
assert(handName(eval7(C(['Ah', 'Ad', '2c', '7s', '9d', 'Jh', 'Qc']))) === 'pair', 'name pair');

// --- эквити: известные значения ---
const rng = makeRng(42);
// AKs vs random HU ≈ 0.670 (Pineapple-таблицы: ~67%)
let e = equityVsRandom(C(['As', 'Ks']), [], 1, 20000, rng);
assert(Math.abs(e.equity - 0.67) < 0.02, `AKs vs random HU equity=${e.equity.toFixed(3)} (~0.67)`);
// 72o vs random HU ≈ 0.349
e = equityVsRandom(C(['7d', '2c']), [], 1, 20000, rng);
assert(Math.abs(e.equity - 0.349) < 0.02, `72o vs random HU equity=${e.equity.toFixed(3)} (~0.349)`);
// AA vs random HU ≈ 0.852
e = equityVsRandom(C(['As', 'Ah']), [], 1, 20000, rng);
assert(Math.abs(e.equity - 0.852) < 0.02, `AA vs random HU equity=${e.equity.toFixed(3)} (~0.852)`);
// AA на ривере против 1 рандомной руки с доской без совпадений должна быть ~0.9+ когда доска чистая
// сет > две пары на флопе конкретно:
const heroSet = C(['As', 'Ah']);
const flop = C(['Ad', 'Kc', '2d']);
e = equityVsRandom(heroSet, flop, 1, 20000, rng);
assert(e.equity > 0.92, `AA+set on A32r equity=${e.equity.toFixed(3)} (>0.92)`);
// speed-тест
const t0 = Date.now();
for (let i = 0; i < 200; i++) equityVsRandom(C(['As', 'Ks']), C(['Qh', '7c', '2s']), 1, 1500, rng);
const dt = Date.now() - t0;
console.log(`  speed: 200 состояний × 1500 ролаутов = ${dt}ms (${(300000 / dt * 1000).toFixed(0)} eval7/s)`);

if (fails) { console.error(`\n${fails} тестов упало`); process.exit(1); }
console.log('\nвсе sanity-тесты движка пройдены');
