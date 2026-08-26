/*
game.js

Playable web prototype engine: JS port of the Python simulation.
Includes: StoryState, ButterflyEffectSystem, Persona layer, intent mapper,
heroine_favor -> ethan_strength logic, UI bindings, and automated playstyles.

This file is intentionally self-contained and deterministic.
*/

// ---------- Utilities ----------
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function floor(v) { return Math.floor(v); }

// ---------- Core State & Engine ----------
class StoryState {
  constructor(difficulty='medium'){
    this.difficulty = difficulty;
    if (this.difficulty === 'easy'){
      this.stat_multiplier = 0.7; this.system_points = 150; this.ethan_hostility = 0; this.nicole_pressure = 20;
    } else if (this.difficulty === 'hard'){
      this.stat_multiplier = 1.5; this.system_points = 50; this.ethan_hostility = 40; this.nicole_pressure = 70;
    } else { this.stat_multiplier = 1.0; this.system_points = 100; this.ethan_hostility = 10; this.nicole_pressure = 40; }

    this.stats = {
      nicole_trust: 50,
      ethan_hostility: this.ethan_hostility,
      nicole_pressure: this.nicole_pressure,
      heroine_favor: 0,
      system_points: this.system_points,
    };
    this.flags = {
      engaged_to_nicole: false,
      saved_heroines: false,
      gala_clown_outfit: false,
      ethan_bankrupted: false,
      legal_sabotage: false,
      ethan_ambush_ready: false,
    };
    this.inventory = [];
  }
  modify_stat(stat, value){
    if (value < 0) value = Math.trunc(value * this.stat_multiplier);
    if (stat in this.stats) this.stats[stat] = clamp(this.stats[stat] + value, 0, 100);
  }
  set_flag(k,v=true){ this.flags[k]=v; }
}

class NarrativeNode {
  constructor(id,text,choices){ this.node_id=id; this.text=text; this.choices=choices; }
}

// ---------- Butterfly System ----------
class ButterflyEffectSystem {
  constructor(){ this.logs = []; this.outcome_modifiers = {}; }
  reset(){ this.logs = []; this.outcome_modifiers = {}; }
  apply_rules_before_node(node, state){
    let disabled = [];
    this.outcome_modifiers = {};
    // Rule A
    if (!state.flags.engaged_to_nicole && state.stats.nicole_pressure >= 50){
      if (!state.flags.legal_sabotage){ state.set_flag('legal_sabotage', true); this.logs.push('Rule A: Legal sabotage activated.'); }
    }
    // Rule B
    if (state.stats.ethan_hostility >= 80){
      for(let i=0;i<node.choices.length;i++){ let ch=node.choices[i]; let t=ch.text.toLowerCase();
        if (t.includes('direct')||t.includes('confront')){ disabled.push(i); this.logs.push(`Rule B: Direct confrontation disabled at ${node.node_id}.`); if (!state.flags.ethan_ambush_ready){ state.set_flag('ethan_ambush_ready', true); this.logs.push('  - Ethan ambush set.'); } }
      }
    }
    // Rule C
    if (state.flags.saved_heroines){ if (state.stats.nicole_trust < 40){ state.modify_stat('nicole_pressure', +5); this.logs.push('Rule C: Saving heroines increased Nicole pressure.'); }
      this.outcome_modifiers['auction_influence']=10; this.logs.push('Rule C: Auction influence +10 from heroines'); }
    // Rule D
    if (state.flags.legal_sabotage){ this.outcome_modifiers['legal_sabotage_penalty'] = -20; this.logs.push('Rule D: Legal sabotage will apply -20 penalty.'); }
    // Rule E
    if (state.stats.nicole_pressure >= 75){ this.outcome_modifiers['nicole_pressure_penalty'] = -15; this.logs.push('Rule E: Nicole pressure penalty active (-15).'); }
    return disabled;
  }
  apply_rules_before_outcome(node_id, state, base_success, context=''){
    let score = base_success ? 100 : 0;
    score += (this.outcome_modifiers['auction_influence']||0);
    score += (this.outcome_modifiers['legal_sabotage_penalty']||0);
    score += (this.outcome_modifiers['nicole_pressure_penalty']||0);
    score += Math.trunc((state.stats.system_points - 50)/1.5);
    if (state.flags.ethan_ambush_ready && node_id === 'act3_gala'){ score -= 40; this.logs.push('Rule: Ethan ambush penalized gala (-40).'); }
    let final = score >= 80;
    this.logs.push(`Outcome calc ${context||node_id}: base=${base_success}, score=${score} -> ${final?'SUCCESS':'FAIL'}`);
    return final;
  }
}

// ---------- Personas ----------
class Persona {
  constructor(id,name,templates,modifiers){ this.id=id; this.name=name; this.templates=templates; this.modifiers=modifiers; }
  scene_text(state,node){ return `[${this.name}] ${this.templates.scene(state,node)}`; }
  post_choice_text(state,node,choice){ return `[${this.name}] ${this.templates.post_choice(state,node,choice)}`; }
  apply_modifiers(hook,state){ let logs=[]; let c = this.modifiers[hook]||{}; for(let k in c){ state.modify_stat(k,c[k]); logs.push(`${this.name} applied ${c[k]>0?'+':''}${c[k]} to ${k}`); } return logs; }
}

const PERSONAS = {
  neutral: new Persona('neutral','Narrator', {scene:(s,n)=>n.text, post_choice:(s,n,c)=>`You chose: ${c.text}`}, {}),
  nicole: new Persona('nicole','Nicole',{scene:(s,n)=>`Nicole watches you with a composed smile. (Nicole pressure: ${s.stats.nicole_pressure})`, post_choice:(s,n,c)=>`Nicely calculated. The family will note: ${c.text}`}, {on_accept_engagement:{nicole_trust:10, system_points:5}, on_refuse_engagement:{nicole_pressure:10}}),
  wendy: new Persona('wendy','Wendy/Jessica',{scene:(s,n)=>`The heroines would appreciate kindness — small compassion can change hearts.`, post_choice:(s,n,c)=>`That's compassionate. People will remember it. (Choice: ${c.text})`}, {on_save_heroines:{heroine_favor:10, system_points:5}}),
  ethan: new Persona('ethan','Ethan',{scene:(s,n)=>`Ethan's ideals color the room — expect rivals to act with conviction.`, post_choice:(s,n,c)=>`A bold choice. Heroes don't always play nice. (Choice: ${c.text})`}, {on_save_heroines:{ethan_hostility:10}}),
};

// ---------- Engine logic & nodes ----------
class StoryEngine {
  constructor(difficulty='medium', persona_id='neutral'){
    this.state = new StoryState(difficulty);
    this.nodes = {};
    this.butterfly = new ButterflyEffectSystem();
    this.persona = PERSONAS[persona_id] || PERSONAS['neutral'];
  }
  add_node(node){ this.nodes[node.node_id] = node; }
  compute_ending(){
    let req = (this.state.difficulty==='easy')?50:100;
    if (this.state.flags.ethan_bankrupted && this.state.flags.engaged_to_nicole && this.state.stats.system_points>=req) return 'TRUE ENDING: Absolute Villain Supremacy';
    if (this.state.flags.ethan_bankrupted) return 'ENDING: Solitary Rogue';
    return 'GAME OVER: Total Plot Erasure';
  }
}

function build_engine(difficulty='medium', persona='neutral'){
  let e = new StoryEngine(difficulty, persona);
  e.add_node(new NarrativeNode('act1_morning','You wake up next to Nicole Rivers. She demands an immediate public engagement announcement.', [
    {text:'Accept the engagement.', next_node:'act2_heroines', effect:accept_engagement_effect, hook:'on_accept_engagement'},
    {text:'Refuse and try to escape her family influence.', next_node:'act2_heroines', effect:refuse_engagement_effect, hook:'on_refuse_engagement'}
  ]));
  e.add_node(new NarrativeNode('act2_heroines','You spot Wendy Taylor and Jessica Snow trapped in a dangerous situation. Ethan Knight is en route to rescue them.', [
    {text:'Intervene using System Martial Arts to rescue them first.', next_node:'act3_gala', effect:save_heroines_effect, hook:'on_save_heroines'},
    {text:'Ignore them and let Ethan Knight take the spotlight.', next_node:'act3_gala', effect:ignore_heroines_effect, hook:'on_ignore_heroines'}
  ]));
  e.add_node(new NarrativeNode('act3_gala','At the Investment Gala, Ethan Knight makes his play for absolute power.', [
    {text:`Dress as a 'clown' and disrupt the auction.`, next_node:'ending', effect:auction_clown_effect, hook:'on_gala_auction'},
    {text:'Confront Ethan directly in martial combat.', next_node:'ending', effect:direct_fight_effect, hook:'on_gala_fight'}
  ]));
  e.add_node(new NarrativeNode('ending','', []));
  return e;
}

// ---------- Effects (same logic as Python, ported) ----------
function accept_engagement_effect(state){ state.set_flag('engaged_to_nicole', true); state.modify_stat('nicole_trust',+30); state.modify_stat('system_points',+50); if (!state.inventory.includes('Absolute Defense Card')) state.inventory.push('Absolute Defense Card'); }
function refuse_engagement_effect(state){ state.set_flag('engaged_to_nicole', false); state.modify_stat('nicole_trust',-40); state.modify_stat('nicole_pressure',+30); state.modify_stat('ethan_hostility',+30); }
function save_heroines_effect(state){ state.set_flag('saved_heroines', true); state.modify_stat('heroine_favor',+40); state.modify_stat('ethan_hostility',+40); }
function ignore_heroines_effect(state){ state.set_flag('saved_heroines', false); state.modify_stat('system_points',+20); }

function auction_clown_effect(state, butterfly){
  let base = (state.difficulty==='hard') ? (state.flags.engaged_to_nicole && state.stats.system_points>=100) : (state.flags.engaged_to_nicole || state.stats.system_points>=80);
  // heroine influence reduces ethan strength later; apply butterfly
  let final = butterfly.apply_rules_before_outcome('act3_gala', state, base, 'auction');
  state.set_flag('ethan_bankrupted', final);
}

function direct_fight_effect(state, butterfly){
  let base = state.inventory.includes('Absolute Defense Card');
  let final = butterfly.apply_rules_before_outcome('act3_gala', state, base, 'direct_fight');
  state.set_flag('ethan_bankrupted', final);
}

// ---------- Derived mechanics: heroine_favor -> ethan_strength ----------
function compute_ethan_strength(state){
  // simple formula: ethan_strength = max(0, ethan_hostility - floor(heroine_favor/5))
  return Math.max(0, state.stats.ethan_hostility - Math.floor(state.stats.heroine_favor/5));
}

// ---------- Intent mapper & suggest options ----------
function map_intent(text, node){
  if (!text) return null;
  let t = text.toLowerCase();
  const map = [
    {k:['yes','accept','marry','engage'],'intent':'accept_engagement'},
    {k:['no','refuse','run','escape','leave'],'intent':'refuse_engagement'},
    {k:['save','help','rescue','protect'],'intent':'save_heroines'},
    {k:['ignore','let','leave them'],'intent':'ignore_heroines'},
    {k:['clown','disrupt','auction','auctioneer','outbid'],'intent':'auction_clown'},
    {k:['fight','confront','attack','duel'],'intent':'direct_fight'},
  ];
  for(let m of map){ for(let kw of m.k){ if (t.includes(kw)) return m.intent; } }
  return null;
}

function suggest_options_for(node, persona, state){
  // Deterministic suggestions based on node id and persona
  const templates = {
    'act1_morning':["I should accept — it secures protection.", "I will refuse and disappear.", "Ask for time to think."],
    'act2_heroines':["I'll jump in and save them.", "I'll let Ethan handle it.", "Distract the attackers and escape."],
    'act3_gala':["Cause a scene and disrupt bids.", "Face Ethan in combat.", "Try to sway bidders quietly."]
  };
  let base = templates[node.node_id] || ["Say nothing."];
  // Bias: if persona is wendy, prefer heroine-friendly options first
  if (persona.id === 'wendy' && node.node_id==='act2_heroines') return [base[0], base[2], base[1]];
  if (persona.id === 'nicole' && node.node_id==='act1_morning') return [base[1], base[0], base[2]]; // Nicole may push for acceptance subtly
  return base;
}

// ---------- UI Integration ----------
let engine = null;
let currentNode = null;

function $(id){ return document.getElementById(id); }

function appendLog(line){
  let c = $('logContent');
  let p = document.createElement('div'); p.textContent = line; c.prepend(p);
}

function updateStatePanel(){
  let s = engine.state;
  $('stats').innerHTML = `Nicole Trust: ${s.stats.nicole_trust}<br>Ethan Hostility: ${s.stats.ethan_hostility}<br>Nicole Pressure: ${s.stats.nicole_pressure}<br>Heroine Favor: ${s.stats.heroine_favor}<br>System Points: ${s.stats.system_points}`;
  let ethan_strength = compute_ethan_strength(s);
  $('derived').innerHTML = `Derived Ethan Strength: ${ethan_strength}`;
  $('inventory').textContent = s.inventory.join(', ');
  $('flags').innerHTML = Object.entries(s.flags).map(([k,v])=>`${k}: ${v}`).join('<br>');
}

function setSceneText(text){ $('sceneText').textContent = text; }

function renderChoices(node){
  let container = $('choices'); container.innerHTML='';
  node.choices.forEach((ch,idx)=>{
    let btn = document.createElement('button'); btn.textContent = ch.text; btn.onclick = ()=>handleChoice(idx);
    container.appendChild(btn);
  });
}

function startGame(){
  let diff = $('difficulty').value; let personaId = $('persona').value;
  engine = build_engine(diff, personaId);
  currentNode = 'act1_morning';
  engine.butterfly.reset();
  $('logContent').innerHTML='';
  appendLog(`Game started: difficulty=${diff}, persona=${personaId}`);
  gotoNode(currentNode);
}

function gotoNode(nodeId){
  currentNode = nodeId;
  let node = engine.nodes[nodeId];
  if (!node){ appendLog('End reached.'); setSceneText('End of narrative.'); return; }
  // per-turn decay
  if (engine.state.difficulty === 'hard'){ engine.state.modify_stat('nicole_pressure', +10); engine.state.modify_stat('system_points', -10); }
  // persona scene text
  appendLog(engine.persona.scene_text(engine.state, node));
  // butterfly checks
  let disabled = engine.butterfly.apply_rules_before_node(node, engine.state);
  engine.butterfly.logs.forEach(l=>appendLog(l)); engine.butterfly.logs=[];
  // render choices (disabled choices will be greyed out)
  setSceneText(node.text);
  renderChoices(node);
  // disable buttons as needed
  let btns = $('choices').querySelectorAll('button'); btns.forEach((b,i)=>{ if (disabled.includes(i)){ b.disabled=true; b.style.opacity=0.5; } else { b.disabled=false; b.style.opacity=1.0; } });
  updateStatePanel();
}

function handleChoice(choiceIdx){
  let node = engine.nodes[currentNode];
  if (!node) return;
  let choice = node.choices[choiceIdx];
  // execute effect
  if (choice.effect.length === 2) { choice.effect(engine.state, engine.butterfly); } else { choice.effect(engine.state); }
  appendLog(`Choice made: ${choice.text}`);
  // persona modifiers
  if (choice.hook){ let p_logs = engine.persona.apply_modifiers(choice.hook, engine.state); p_logs.forEach(l=>appendLog(l)); }
  // persona post-commentary
  appendLog(engine.persona.post_choice_text(engine.state, node, choice));
  // capture butterfly logs if any
  engine.butterfly.logs.forEach(l=>appendLog(l)); engine.butterfly.logs=[];
  // After effects, if this was act3_gala's auction or fight we may want to log derived calculations
  if (currentNode==='act3_gala'){
    // compute heroine influence and ethan strength
    let ethan_str = compute_ethan_strength(engine.state);
    let heroine_influence = Math.floor(engine.state.stats.heroine_favor/4) + (engine.butterfly.outcome_modifiers['auction_influence']||0);
    appendLog(`Derived: heroine_influence=${heroine_influence}, ethan_strength=${ethan_str}`);
  }
  updateStatePanel();
  // go to next node
  if (choice.next_node) gotoNode(choice.next_node);
}

function submitFreeForm(){
  let txt = $('playerReply').value.trim(); if (!txt) return;
  let node = engine.nodes[currentNode];
  appendLog(`Player replied (free-form): ${txt}`);
  let intent = map_intent(txt, node);
  if (!intent){ appendLog('No clear intent detected. Try suggested options or pick a choice.'); return; }
  // map intent to choice index
  let mapping = {accept_engagement:0, refuse_engagement:1, save_heroines:0, ignore_heroines:1, auction_clown:0, direct_fight:1};
  let idx = mapping[intent]; appendLog(`Mapped free-form to intent '${intent}' -> choice ${idx}`);
  // execute
  handleChoice(idx);
}

function suggestOptions(){
  let node = engine.nodes[currentNode]; if (!node) return;
  let suggestions = suggest_options_for(node, engine.persona, engine.state);
  // show suggestions (replace choices area with suggestion buttons)
  let container = $('choices'); container.innerHTML='';
  suggestions.forEach((s,idx)=>{ let btn=document.createElement('button'); btn.textContent = s; btn.onclick = ()=>{ $('playerReply').value = s; }; container.appendChild(btn); });
  appendLog('Suggested options generated. Click one to copy into the reply box.');
}

// Automated playstyles runner (for designers)
const PLAYSTYLES = {
  'Shadow Strategist':[ ['act1_morning',0], ['act2_heroines',0], ['act3_gala',0] ],
  'Puppet of the Ice Queen':[ ['act1_morning',0], ['act2_heroines',1], ['act3_gala',0] ],
  'Erased by the Plot':[ ['act1_morning',1], ['act2_heroines',1], ['act3_gala',1] ],
  'Solitary Rogue':[ ['act1_morning',1], ['act2_heroines',0], ['act3_gala',1] ],
};

function runAutomated(){
  let personaId = $('persona').value; let diff=$('difficulty').value;
  for(let pname in PLAYSTYLES){ appendLog('--- Automated run: '+pname+' ---'); let seq=PLAYSTYLES[pname]; let eng = build_engine(diff, personaId); eng.butterfly.reset(); eng.persona = PERSONAS[personaId]; for(let step of seq){
    let [nodeId, cidx] = step; // apply per-turn decay if hard
    if (eng.state.difficulty==='hard'){ eng.state.modify_stat('nicole_pressure',+10); eng.state.modify_stat('system_points',-10); }
    let node = eng.nodes[nodeId]; appendLog(eng.persona.scene_text(eng.state,node)); let disabled = eng.butterfly.apply_rules_before_node(node, eng.state); eng.butterfly.logs.forEach(l=>appendLog(l)); eng.butterfly.logs=[];
    if (disabled.includes(cidx)){ appendLog(`Choice ${cidx} disabled, falling back.`); let enabled = [...Array(node.choices.length).keys()].filter(i=>!disabled.includes(i)); if (enabled.length===0){ appendLog('No choices available; stopping.'); break; } cidx = enabled[0]; }
    let choice = node.choices[cidx]; if (choice.effect.length===2) choice.effect(eng.state, eng.butterfly); else choice.effect(eng.state);
    if (choice.hook){ let p_logs = eng.persona.apply_modifiers(choice.hook, eng.state); p_logs.forEach(l=>appendLog(l)); }
    appendLog(eng.persona.post_choice_text(eng.state,node,choice)); eng.butterfly.logs.forEach(l=>appendLog(l)); eng.butterfly.logs=[];
  }
  appendLog('Result: '+eng.compute_ending()); appendLog(`Final stats: ${JSON.stringify(eng.state.stats)}`);
  }
}

// ---------- Wiring to DOM ----------
document.addEventListener('DOMContentLoaded', ()=>{
  $('restartBtn').addEventListener('click', ()=>startGame());
  $('submitReply').addEventListener('click', ()=>submitFreeForm());
  $('suggestBtn').addEventListener('click', ()=>suggestOptions());
  $('autoBtn').addEventListener('click', ()=>{ runAutomated(); });
  // start default
  startGame();
});
