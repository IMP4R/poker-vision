#!/usr/bin/env node
// CrazyPanda World Poker Club → CDP/WebSocket decoder → Jev/NanoGPT move advisor.
// Read-only: never clicks Fold/Call/Raise and never sends game WebSocket frames.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CDP = process.env.CDP || 'http://127.0.0.1:9222';
const HERO_DEFAULT = '147502575_';
const HERO_NAME = 'Spooky Master';
const credentials = fs.readFileSync(path.join(os.homedir(), '.dsh', '.credentials.yaml'), 'utf8');
const keyMatch = credentials.match(/^NANO_GPT_API_KEY:\s*['"]?([^'"\n]+)/m);
if (!keyMatch) throw new Error('NANO_GPT_API_KEY не найден в ~/.dsh/.credentials.yaml');
const NANO_KEY = keyMatch[1].trim();

const RANKS = '23456789TJQKA';
// Названия мастей условны, но mapping полностью консистентен между рукой и бордом.
const SUITS = 'shdc';
const cardStr = n => RANKS[n % 13] + SUITS[Math.floor(n / 13)];
const pct = x => `${Math.round(Number(x || 0) * 100)}%`;
const sleep = ms => new Promise(r => setTimeout(r, ms));

let heroId = process.env.HERO_ID || HERO_DEFAULT;
const places = new Map();
let hand = freshHand();
let lastAdviceTurn = '';
let adviceInFlight = false;

function freshHand() {
  return {
    match: null, heroCards: [], board: [], players: [], dealerPlace: null,
    sb: 5, contributions: new Map(), stacks: new Map(), actions: [],
    equity: null, handType: null, pot: 0, street: 'preflop', startedAt: 0,
  };
}

function decodeFrame(payload, opcode) {
  let buf;
  try { buf = opcode === 2 ? Buffer.from(payload, 'base64') : Buffer.from(payload); }
  catch { return null; }
  const a = buf.indexOf(0x7b), z = buf.lastIndexOf(0x7d);
  if (a < 0 || z < a) return null;
  try { return JSON.parse(buf.subarray(a, z + 1).toString('utf8')); }
  catch { return null; }
}

function actionName(e) {
  if (e.blind) return `blind ${e.add_coins}`;
  if (e.type === 1) return 'fold';
  if (e.type === 4) return Number(e.add_coins || 0) > 0 ? `call ${e.add_coins}` : 'check';
  if (e.type === 8) return `raise/bet ${e.add_coins || 0}`;
  return `action(type=${e.type}, add=${e.add_coins || 0})`;
}

function allowedNames(mask) {
  const out = [];
  if (mask & 1) out.push('fold');
  if (mask & 2) out.push('check');
  if (mask & 4) out.push('call');
  if (mask & 8) out.push('raise');
  return out;
}

function positionOfHero() {
  const hp = places.get(heroId);
  if (hp == null || hand.dealerPlace == null) return 'unknown';
  if (hp === hand.dealerPlace) return hand.players.length === 2 ? 'BTN/SB' : 'BTN';
  const active = hand.players.map(id => ({ id, p: places.get(id) })).filter(x => x.p != null);
  if (!active.length) return `seat-${hp}`;
  const ordered = active.sort((a,b) => ((a.p - hand.dealerPlace + 10) % 10) - ((b.p - hand.dealerPlace + 10) % 10));
  const idx = ordered.findIndex(x => x.id === heroId);
  if (idx === 1) return 'SB';
  if (idx === 2 || (hand.players.length === 2 && idx === 1)) return 'BB';
  const remaining = ordered.length - idx;
  if (remaining === 2) return 'CO';
  if (remaining === 3) return 'MP';
  return 'UTG';
}

function potValue() {
  const sum = [...hand.contributions.values()].reduce((a,b) => a + Number(b || 0), 0);
  return Math.max(hand.pot || 0, sum);
}

function streetFromBoard() {
  if (!hand.board.length) return 'preflop';
  if (hand.board.length === 3) return 'flop';
  if (hand.board.length === 4) return 'turn';
  return 'river';
}

function choiceCriteria(allowed, ev) {
  const c = {};
  if (allowed.includes('fold')) c.fold = 'сбросить карты; отказаться от банка';
  if (allowed.includes('check')) c.check = 'чек; продолжить без дополнительной ставки';
  if (allowed.includes('call')) c.call = `уравнять ${ev.call_value} фишек`;
  if (allowed.includes('raise')) c.raise = `рейз; минимальный серверный размер ${ev.raise_value} фишек`;
  return c;
}

async function askJev(turn) {
  const bb = hand.sb * 2 || 10;
  const allowed = allowedNames(turn.allowed);
  const state = {
    game: 'texas_holdem_cash_play_money',
    source: 'CrazyPanda World Poker Club server protocol',
    hero: HERO_NAME,
    hero_cards: hand.heroCards.map(cardStr),
    board: hand.board.map(cardStr),
    street: streetFromBoard(),
    position: positionOfHero(),
    active_players: hand.players.length,
    dealer_seat: hand.dealerPlace,
    hero_seat: places.get(heroId),
    pot_chips: potValue(), pot_bb: +(potValue() / bb).toFixed(2),
    to_call_chips: Number(turn.call_value || 0), to_call_bb: +(Number(turn.call_value || 0) / bb).toFixed(2),
    stack_chips: Number(turn.cash || 0), stack_bb: +(Number(turn.cash || 0) / bb).toFixed(2),
    min_raise_chips: Number(turn.raise_value || 0),
    allowed_actions: allowed,
    server_equity_percent: Number.isFinite(hand.equity) ? hand.equity : null,
    server_hand_type: hand.handType,
    action_history: hand.actions.slice(-20),
  };
  const questions = {
    action: {
      type: 'choice',
      instructions: 'Выбери оптимальное действие героя в техасском холдеме. Это игровые фишки без вывода денег. Используй позицию, диапазоны, pot odds, stack-to-pot ratio, server equity, историю ставок и только реально разрешённые кнопки.',
      criteria: choiceCriteria(allowed, turn),
    },
  };
  const started = Date.now();
  const res = await fetch('https://nano-gpt.com/api/v1/chat/completions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${NANO_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'typesafe/jev-1.13',
      messages: [{ role: 'user', content: JSON.stringify(state) }],
      response_format: { type: 'questions', questions },
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error?.message || `NanoGPT HTTP ${res.status}`);
  const answers = JSON.parse(data.choices?.[0]?.message?.content || '{}');
  return { answer: answers.action || {}, state, usage: data.usage || {}, latency: Date.now() - started, model: data.model };
}

function renderAdvice(result) {
  const a = result.answer;
  const sorted = Object.entries(a.probabilities || {}).sort((x,y) => y[1] - x[1]);
  const s = result.state;
  const top = String(a.choice || 'UNKNOWN').toUpperCase();
  const color = top === 'FOLD' ? '\x1b[31m' : top === 'RAISE' ? '\x1b[33m' : '\x1b[32m';
  console.log('\n\x1b[1;36m════════════ ТВОЙ ХОД ════════════\x1b[0m');
  console.log(`Карты: \x1b[1m${s.hero_cards.join(' ')}\x1b[0m   Борд: ${s.board.join(' ') || '—'}   ${s.street}`);
  console.log(`Позиция: ${s.position}   игроков: ${s.active_players}   банк: ${s.pot_chips} (${s.pot_bb}bb)`);
  console.log(`Колл: ${s.to_call_chips} (${s.to_call_bb}bb)   стек: ${s.stack_chips} (${s.stack_bb}bb)   equity игры: ${s.server_equity_percent ?? '—'}%`);
  console.log(`${color}\x1b[1m→ ${top}\x1b[0m`);
  for (const [move,p] of sorted) console.log(`  ${move.padEnd(7)} ${pct(p)}`);
  console.log(`Уверенность: ${pct(a.confidence)}   latency: ${result.latency}ms   cost: $${Number(result.usage.cost || 0).toFixed(8)}`);
  console.log('\x1b[1;36m═══════════════════════════════════\x1b[0m\n');
  process.stdout.write('\x07');
}

async function onEvent(e) {
  if (e.client?.id && (e.client?.user?.name === HERO_NAME || String(e.client.id).startsWith(HERO_DEFAULT))) heroId = e.client.id;
  if (e.name === 'game_started' && !hand.match && (e.players || []).some(id => String(id).startsWith(HERO_DEFAULT))) heroId = (e.players || []).find(id => String(id).startsWith(HERO_DEFAULT));
  if (e.name === 'game_cash_set' && e.client != null && e.place != null) places.set(String(e.client), e.place);
  if (e.name === 'table_user_entered' && e.client?.id != null && e.client?.place != null) places.set(String(e.client.id), e.client.place);

  if (e.name === 'game_started') {
    const prevPlaces = new Map(places);
    hand = freshHand();
    for (const [k,v] of prevPlaces) places.set(k,v);
    hand.match = e.match_id;
    hand.heroCards = e.my_cards || [];
    const myId = (e.players || []).find(id => String(id).startsWith(HERO_DEFAULT));
    if (myId) heroId = myId;
    hand.players = e.players || [];
    hand.dealerPlace = e.dealer;
    hand.sb = Number(e.sb_value || 5);
    hand.equity = Number(e.my_hand?.equity ?? e.my_hand?.probs?.odds ?? NaN);
    hand.handType = e.my_hand?.type ?? null;
    hand.startedAt = Date.now();
    if (e.cash != null) hand.stacks.set(heroId, e.cash);
    console.log(`\n[hand ${hand.match}] ${hand.heroCards.length ? hand.heroCards.map(cardStr).join(' ') : '(наблюдение)'} · игроков ${hand.players.length}`);
    return;
  }
  if (e.name === 'game_move_finished') {
    if (e.id) {
      if (e.total_coins != null) hand.contributions.set(e.id, Number(e.total_coins));
      if (e.cash != null) hand.stacks.set(e.id, Number(e.cash));
      hand.actions.push({ player: e.id === heroId ? 'hero' : e.id, action: actionName(e), total: e.total_coins, cash: e.cash });
    }
    return;
  }
  if (e.name === 'game_round_finished') {
    hand.pot = (e.pots || []).reduce((a,b) => a + Number(b || 0), 0);
    return;
  }
  if (e.name === 'game_round_started') {
    if (e.table_cards) hand.board = e.table_cards;
    hand.street = streetFromBoard();
    if (e.my_hand) {
      hand.equity = Number(e.my_hand.equity ?? e.my_hand?.probs?.odds ?? hand.equity);
      hand.handType = e.my_hand.type ?? hand.handType;
    }
    return;
  }
  if (e.name === 'game_end') {
    hand.match = null;
    return;
  }
  if (e.name === 'game_start_move' && String(e.id).startsWith(HERO_DEFAULT) && hand.match && hand.heroCards.length === 2) {
    const turnKey = `${hand.match}:${e.T}:${e.call_value}:${e.allowed}`;
    if (turnKey === lastAdviceTurn || adviceInFlight) return;
    lastAdviceTurn = turnKey;
    adviceInFlight = true;
    try { renderAdvice(await askJev(e)); }
    catch (err) { console.error('[Jev error]', err.message); }
    finally { adviceInFlight = false; }
  }
}

const version = await fetch(`${CDP}/json/version`).then(r => r.json());
const ws = new WebSocket(version.webSocketDebuggerUrl);
let seq = 1;
const sessions = new Map(), attached = new Set(), pending = new Map();
function send(method, params = {}, sessionId) {
  const msg = { id: seq++, method, params };
  if (sessionId) msg.sessionId = sessionId;
  ws.send(JSON.stringify(msg)); return msg.id;
}
ws.onopen = () => {
  console.log(`[advisor] Chrome ${version.Browser}; hero=${heroId}; read-only mode`);
  send('Target.setDiscoverTargets', { discover: true });
  send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: false, flatten: true });
  const q = send('Target.getTargets'); pending.set(q, true);
};
ws.onmessage = async ev => {
  let m; try { m = JSON.parse(ev.data); } catch { return; }
  if (m.id && pending.has(m.id)) {
    pending.delete(m.id);
    for (const t of m.result?.targetInfos || []) if (['page','iframe','worker'].includes(t.type) && !attached.has(t.targetId)) {
      attached.add(t.targetId); send('Target.attachToTarget', { targetId:t.targetId, flatten:true });
    }
    return;
  }
  if (m.method === 'Target.targetCreated') {
    const t=m.params.targetInfo;
    if (['page','iframe','worker'].includes(t.type) && !attached.has(t.targetId)) { attached.add(t.targetId); send('Target.attachToTarget',{targetId:t.targetId,flatten:true}); }
    return;
  }
  if (m.method === 'Target.attachedToTarget') {
    const {sessionId,targetInfo}=m.params; sessions.set(sessionId,targetInfo);
    send('Network.enable',{maxTotalBufferSize:100000000,maxResourceBufferSize:10000000},sessionId);
    return;
  }
  if (m.method === 'Network.webSocketFrameReceived') {
    const e=decodeFrame(m.params.response.payloadData,m.params.response.opcode);
    if(e) await onEvent(e);
  }
};
ws.onerror = e => console.error('[CDP error]', e.message || e);
process.on('SIGINT',()=>{ws.close();process.exit(0)});
await new Promise(()=>{});
