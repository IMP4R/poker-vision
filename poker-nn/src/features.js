// Кодирование состояния в вектор признаков для MLP.
// Версия признаков фиксируется в weight.json (featureVersion).
export const POSITIONS = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'];
export const STREETS = ['preflop', 'flop', 'turn', 'river'];

export function featureVersion() { return 1; }

export function encode(s) {
  // s = { hero:[c1,c2], board:[...0..5], position: idx, numPlayers, aggressors,
  //       potBB, toCallBB, stackBB, facing: 'none'|'limp'|'raise'|'3bet'|'4bet' }
  const x = [];
  // hero cards (2 × 52)
  for (let i = 0; i < 52; i++) x.push(s.hero[0] === i ? 1 : 0);
  for (let i = 0; i < 52; i++) x.push(s.hero[1] === i ? 1 : 0);
  // board (5 × 52, замаскировано)
  for (let i = 0; i < 5; i++) {
    const c = s.board[i];
    for (let j = 0; j < 52; j++) x.push(c !== undefined && c !== null && c === j ? 1 : 0);
  }
  const street = STREETS[Math.min(3, Math.max(0, s.board.length === 0 ? 0 : s.board.length === 3 ? 1 : s.board.length === 4 ? 2 : 3))];
  // street one-hot
  x.push(street === 'preflop' ? 1 : 0, street === 'flop' ? 1 : 0, street === 'turn' ? 1 : 0, street === 'river' ? 1 : 0);
  // позиция one-hot
  for (const p of POSITIONS) x.push(POSITIONS[s.position] === p ? 1 : 0);
  // число игроков, агрессоры
  x.push(clamp(s.numPlayers, 2, 6) / 6);
  x.push(clamp(s.aggressors, 0, 3) / 3);
  // банк, размер колла, SPR
  x.push(Math.log(1 + clamp(s.potBB, 0, 300)) / Math.log(301));
  const req = s.toCallBB > 0 ? s.toCallBB / (s.potBB + s.toCallBB) : 0;
  x.push(clamp(req, 0, 1));
  x.push(clamp(s.stackBB / Math.max(s.potBB, 0.5), 0, 25) / 25); // SPR capped
  x.push(clamp(s.stackBB, 0, 200) / 200);
  // facing one-hot
  const fac = ['none', 'limp', 'raise', '3bet', '4bet'];
  for (const f of fac) x.push(s.facing === f ? 1 : 0);
  return Float64Array.from(x);
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

export function inputSize() { return 104 + 260 + 4 + 6 + 3 + 5; } // пересчитывается фактически в encode
