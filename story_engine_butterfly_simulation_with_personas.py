#!/usr/bin/env python3
"""
story_engine_butterfly_simulation_with_personas.py

Simulation harness with a deterministic Butterfly Effect system and
Persona layer for cast-flavored narration and small deterministic biases.

Run examples:
    python3 story_engine_butterfly_simulation_with_personas.py
    python3 story_engine_butterfly_simulation_with_personas.py --persona=nicole

This file is intentionally self-contained for easy review.
"""

from typing import Dict, List, Tuple, Callable, Optional
import argparse


# --------------------------
# Core engine & butterfly
# --------------------------
class StoryState:
    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty.lower()

        if self.difficulty == "easy":
            self.stat_multiplier = 0.7
            self.system_points = 150
            self.ethan_hostility = 0
            self.nicole_pressure = 20
        elif self.difficulty == "hard":
            self.stat_multiplier = 1.5
            self.system_points = 50
            self.ethan_hostility = 40
            self.nicole_pressure = 70
        else:  # medium
            self.stat_multiplier = 1.0
            self.system_points = 100
            self.ethan_hostility = 10
            self.nicole_pressure = 40

        self.stats: Dict[str, int] = {
            "nicole_trust": 50,
            "ethan_hostility": self.ethan_hostility,
            "nicole_pressure": self.nicole_pressure,
            "heroine_favor": 0,
            "system_points": self.system_points,
        }
        self.flags: Dict[str, bool] = {
            "engaged_to_nicole": False,
            "saved_heroines": False,
            "gala_clown_outfit": False,
            "ethan_bankrupted": False,
            # butterfly-driven side-effects
            "legal_sabotage": False,
            "ethan_ambush_ready": False,
        }
        self.inventory: List[str] = []

    def modify_stat(self, stat_name: str, value: int):
        original_value = value
        if value < 0:
            value = int(value * self.stat_multiplier)

        if stat_name in self.stats:
            self.stats[stat_name] = max(0, min(100, self.stats[stat_name] + value))

    def apply_turn_decay(self):
        if self.difficulty == "hard":
            # Hard mode passive effects
            self.modify_stat("nicole_pressure", +10)
            self.modify_stat("system_points", -10)

    def set_flag(self, flag_name: str, status: bool = True):
        self.flags[flag_name] = status

    def debug_summary(self) -> str:
        return (
            f"Stats: {self.stats} | Flags: {self.flags} | Inventory: {self.inventory}"
        )


class NarrativeNode:
    def __init__(self, node_id: str, text: str, choices: List[Dict]):
        self.node_id = node_id
        self.text = text
        self.choices = choices


class ButterflyEffectSystem:
    """
    Deterministic butterfly rules. Rules append human-readable logs and
    may set flags / outcome modifiers.
    """

    def __init__(self):
        self.logs: List[str] = []
        self.outcome_modifiers: Dict[str, int] = {}

    def reset(self):
        self.logs.clear()
        self.outcome_modifiers.clear()

    def apply_rules_before_node(self, node: NarrativeNode, state: StoryState) -> List[int]:
        disabled_indices: List[int] = []
        self.outcome_modifiers.clear()

        # Rule A: Legal sabotage triggers if you're not engaged and Nicole pressure is high
        if not state.flags.get("engaged_to_nicole") and state.stats["nicole_pressure"] >= 50:
            if not state.flags.get("legal_sabotage"):
                state.set_flag("legal_sabotage", True)
                self.logs.append("Rule A fired: Legal sabotage activated (nicole_pressure high & not engaged).")

        # Rule B: If Ethan is highly hostile, disable direct confrontations (ambush)
        if state.stats["ethan_hostility"] >= 80:
            for idx, ch in enumerate(node.choices):
                if "direct" in ch["text"].lower() or "confront" in ch["text"].lower():
                    disabled_indices.append(idx)
                    self.logs.append(f"Rule B fired: Direct confrontation disabled on node '{node.node_id}' due to Ethan hostility.")
                    if not state.flags.get("ethan_ambush_ready"):
                        state.set_flag("ethan_ambush_ready", True)
                        self.logs.append("  - Ethan ambush flag set.")

        # Rule C: Saving heroines grants auction influence but may annoy Nicole if trust is low
        if state.flags.get("saved_heroines"):
            if state.stats["nicole_trust"] < 40:
                state.modify_stat("nicole_pressure", +5)
                self.logs.append("Rule C: Saving heroines increased Nicole pressure due to jealousy.")
            self.outcome_modifiers["auction_influence"] = 10
            self.logs.append("Rule C: Saving heroines grants auction influence +10.")

        # Rule D: Legal sabotage reduces system points at Gala
        if state.flags.get("legal_sabotage"):
            self.outcome_modifiers["legal_sabotage_penalty"] = -20
            self.logs.append("Rule D: Legal sabotage will apply -20 to system points at Gala outcome check.")

        # Rule E: High Nicole pressure makes public success harder
        if state.stats["nicole_pressure"] >= 75:
            self.outcome_modifiers["nicole_pressure_penalty"] = -15
            self.logs.append("Rule E: Nicole pressure penalty active (-15 to relevant checks).")

        return disabled_indices

    def apply_rules_before_outcome(self, node_id: str, state: StoryState, base_success: bool, context: str = "") -> bool:
        score = 0
        score += 100 if base_success else 0
        score += self.outcome_modifiers.get("auction_influence", 0)
        score += self.outcome_modifiers.get("legal_sabotage_penalty", 0)
        score += self.outcome_modifiers.get("nicole_pressure_penalty", 0)
        score += int((state.stats["system_points"] - 50) / 1.5)

        if state.flags.get("ethan_ambush_ready") and node_id == "act3_gala":
            score -= 40
            self.logs.append("Rule: Ethan ambush penalized gala outcome (-40).")

        final_success = score >= 80
        self.logs.append(f"Outcome calc for {context or node_id}: base={base_success}, score={score} -> {'SUCCESS' if final_success else 'FAIL'}")
        return final_success


class Persona:
    """Simple persona model for flavor text and small deterministic biases.

    Each persona provides:
      - id, name
      - text templates for scene/choice/outcome
      - deterministic state_modifiers that are applied in defined contexts
    """

    def __init__(self, pid: str, name: str, templates: Dict[str, Callable], modifiers: Dict[str, Dict[str, int]]):
        self.id = pid
        self.name = name
        self.templates = templates
        # modifiers: e.g., {"on_accept_engagement":{"nicole_trust":+10}}
        self.modifiers = modifiers

    def scene_text(self, state: StoryState, node: NarrativeNode) -> str:
        fn = self.templates.get("scene")
        if fn:
            return f"[{self.name}] {fn(state, node)}"
        return f"[{self.name}]"

    def post_choice_text(self, state: StoryState, node: NarrativeNode, choice: Dict) -> str:
        fn = self.templates.get("post_choice")
        if fn:
            return f"[{self.name}] {fn(state, node, choice)}"
        return f"[{self.name}]"

    def apply_modifiers_for(self, hook: str, state: StoryState) -> List[str]:
        """Apply deterministic modifiers for the named hook and return logs of applied modifiers."""
        logs: List[str] = []
        changes = self.modifiers.get(hook, {})
        for stat, delta in changes.items():
            state.modify_stat(stat, delta)
            logs.append(f"Persona {self.name} applied {delta:+} to {stat}")
        return logs


def persona_neutral_scene(state: StoryState, node: NarrativeNode) -> str:
    return node.text


def persona_neutral_post(state: StoryState, node: NarrativeNode, choice: Dict) -> str:
    return f"You chose: {choice['text']}"


def persona_nicole_scene(state: StoryState, node: NarrativeNode) -> str:
    return (f"Nicole watches you with a composed smile. Public image matters. "
            f"(Nicole pressure: {state.stats['nicole_pressure']})")


def persona_nicole_post(state: StoryState, node: NarrativeNode, choice: Dict) -> str:
    return f"Nicely calculated. The family will note your public decisions. You chose: {choice['text']}"


def persona_wendy_scene(state: StoryState, node: NarrativeNode) -> str:
    return "The heroines would appreciate kindness — small compassion can change hearts."


def persona_wendy_post(state: StoryState, node: NarrativeNode, choice: Dict) -> str:
    return f"That's compassionate. People will remember it. (Choice: {choice['text']})"


def persona_ethan_scene(state: StoryState, node: NarrativeNode) -> str:
    return "Ethan's ideals color the room — expect rivals to act with conviction."


def persona_ethan_post(state: StoryState, node: NarrativeNode, choice: Dict) -> str:
    return f"A bold choice. Heroes don't always play nice. (Choice: {choice['text']})"


# Persona presets (Nicole, Wendy/Jessica, Ethan, Neutral)
PERSONAS: Dict[str, Persona] = {
    "neutral": Persona(
        pid="neutral",
        name="Narrator",
        templates={"scene": persona_neutral_scene, "post_choice": persona_neutral_post},
        modifiers={}
    ),
    "nicole": Persona(
        pid="nicole",
        name="Nicole",
        templates={"scene": persona_nicole_scene, "post_choice": persona_nicole_post},
        modifiers={
            # small deterministic biases
            "on_accept_engagement": {"nicole_trust": +10, "system_points": +5},
            "on_refuse_engagement": {"nicole_pressure": +10},
        },
    ),
    "wendy": Persona(
        pid="wendy",
        name="Wendy/Jessica",
        templates={"scene": persona_wendy_scene, "post_choice": persona_wendy_post},
        modifiers={
            "on_save_heroines": {"heroine_favor": +10, "system_points": +5}
        },
    ),
    "ethan": Persona(
        pid="ethan",
        name="Ethan",
        templates={"scene": persona_ethan_scene, "post_choice": persona_ethan_post},
        modifiers={
            # Ethan persona biases against actions that help heroines
            "on_save_heroines": {"ethan_hostility": +10}
        },
    )
}


class StoryEngine:
    def __init__(self, difficulty: str = "medium", persona: Optional[Persona] = None):
        self.state = StoryState(difficulty)
        self.nodes: Dict[str, NarrativeNode] = {}
        self.butterfly = ButterflyEffectSystem()
        self.persona = persona or PERSONAS["neutral"]

    def add_node(self, node: NarrativeNode):
        self.nodes[node.node_id] = node

    def compute_ending_string(self) -> str:
        required_points = 50 if self.state.difficulty == "easy" else (100 if self.state.difficulty == "medium" else 100)
        if (
            self.state.flags.get("ethan_bankrupted")
            and self.state.flags.get("engaged_to_nicole")
            and self.state.stats["system_points"] >= required_points
        ):
            return "TRUE ENDING: Absolute Villain Supremacy"
        elif self.state.flags.get("ethan_bankrupted"):
            return "ENDING: Solitary Rogue"
        else:
            return "GAME OVER: Total Plot Erasure"

    def reset_state(self, difficulty: str):
        self.state = StoryState(difficulty)
        self.butterfly.reset()


# --------------------------
# Effects used by choices (now consult butterfly & persona)
# --------------------------

def accept_engagement_effect(state: StoryState):
    state.set_flag("engaged_to_nicole", True)
    state.modify_stat("nicole_trust", +30)
    state.modify_stat("system_points", +50)
    if "Absolute Defense Card" not in state.inventory:
        state.inventory.append("Absolute Defense Card")


def refuse_engagement_effect(state: StoryState):
    state.set_flag("engaged_to_nicole", False)
    state.modify_stat("nicole_trust", -40)
    state.modify_stat("nicole_pressure", +30)
    state.modify_stat("ethan_hostility", +30)


def save_heroines_effect(state: StoryState):
    state.set_flag("saved_heroines", True)
    state.modify_stat("heroine_favor", +40)
    state.modify_stat("ethan_hostility", +40)


def ignore_heroines_effect(state: StoryState):
    state.set_flag("saved_heroines", False)
    state.modify_stat("system_points", +20)


def auction_clown_effect(state: StoryState, butterfly: ButterflyEffectSystem):
    if state.difficulty == "hard":
        base_success = state.flags["engaged_to_nicole"] and state.stats["system_points"] >= 100
    else:
        base_success = state.flags["engaged_to_nicole"] or state.stats["system_points"] >= 80

    final_success = butterfly.apply_rules_before_outcome("act3_gala", state, base_success, context="auction")
    state.set_flag("ethan_bankrupted", final_success)


def direct_fight_effect(state: StoryState, butterfly: ButterflyEffectSystem):
    base_success = "Absolute Defense Card" in state.inventory
    final_success = butterfly.apply_rules_before_outcome("act3_gala", state, base_success, context="direct_fight")
    state.set_flag("ethan_bankrupted", final_success)


# --------------------------
# Build sample engine nodes
# --------------------------

def build_sample_engine(difficulty: str = "medium", persona_id: str = "neutral") -> StoryEngine:
    persona = PERSONAS.get(persona_id, PERSONAS["neutral"])
    engine = StoryEngine(difficulty=difficulty, persona=persona)

    engine.add_node(NarrativeNode(
        "act1_morning",
        "You wake up next to Nicole Rivers. She demands an immediate public engagement announcement.",
        [
            {"text": "Accept the engagement.", "next_node": "act2_heroines", "effect": accept_engagement_effect, "hook": "on_accept_engagement"},
            {"text": "Refuse and try to escape her family influence.", "next_node": "act2_heroines", "effect": refuse_engagement_effect, "hook": "on_refuse_engagement"}
        ]
    ))

    engine.add_node(NarrativeNode(
        "act2_heroines",
        "You spot Wendy Taylor and Jessica Snow trapped in a dangerous situation. Ethan Knight is en route to rescue them.",
        [
            {"text": "Intervene using System Martial Arts to rescue them first.", "next_node": "act3_gala", "effect": save_heroines_effect, "hook": "on_save_heroines"},
            {"text": "Ignore them and let Ethan Knight take the spotlight.", "next_node": "act3_gala", "effect": ignore_heroines_effect, "hook": "on_ignore_heroines"}
        ]
    ))

    engine.add_node(NarrativeNode(
        "act3_gala",
        "At the Investment Gala, Ethan Knight makes his play for absolute power.",
        [
            {"text": "Dress as a 'clown' and disrupt the auction.", "next_node": "ending", "effect": auction_clown_effect, "hook": "on_gala_auction"},
            {"text": "Confront Ethan directly in martial combat.", "next_node": "ending", "effect": direct_fight_effect, "hook": "on_gala_fight"}
        ]
    ))

    engine.add_node(NarrativeNode("ending", "", []))
    return engine


# --------------------------
# Playstyles described as sequence of (node_id, choice_index)
# --------------------------
PLAYSTYLES: Dict[str, List[Tuple[str, int]]] = {
    "Shadow Strategist": [("act1_morning", 0), ("act2_heroines", 0), ("act3_gala", 0)],
    "Puppet of the Ice Queen": [("act1_morning", 0), ("act2_heroines", 1), ("act3_gala", 0)],
    "Erased by the Plot": [("act1_morning", 1), ("act2_heroines", 1), ("act3_gala", 1)],
    "Solitary Rogue": [("act1_morning", 1), ("act2_heroines", 0), ("act3_gala", 1)],
}


def simulate_playstyle_with_persona(playstyle_sequence: List[Tuple[str, int]], difficulty: str, persona_id: str, verbose: bool = False) -> Dict:
    engine = build_sample_engine(difficulty, persona_id)
    state = engine.state
    butterfly = engine.butterfly
    persona = engine.persona

    run_log: List[str] = []
    butterfly.reset()

    for node_id, choice_idx in playstyle_sequence:
        # per-turn decay
        state.apply_turn_decay()
        node = engine.nodes.get(node_id)
        if not node:
            run_log.append(f"Node {node_id} not found; stopping.")
            break

        # persona scene flavor
        scene_line = persona.scene_text(state, node)
        run_log.append(scene_line)

        # butterfly checks (may disable choices)
        disabled = butterfly.apply_rules_before_node(node, state)
        if disabled:
            run_log.append(f"Butterfly disabled choices at {node_id}: {disabled}")

        # validate choice
        if choice_idx in disabled:
            run_log.append(f"Requested choice {choice_idx} at {node_id} was disabled by butterfly rules.")
            enabled_indices = [i for i in range(len(node.choices)) if i not in disabled]
            if not enabled_indices:
                run_log.append(f"No choices available at {node_id} after butterfly rules; stopping.")
                break
            fallback_idx = enabled_indices[0]
            run_log.append(f"Falling back to choice {fallback_idx} instead.")
            choice_idx = fallback_idx

        choice = node.choices[choice_idx]

        # run the effect (some effects accept butterfly)
        eff = choice.get("effect")
        if eff:
            try:
                eff(state, butterfly)
            except TypeError:
                eff(state)

        # persona applies deterministic modifiers for the hook if any
        hook = choice.get("hook")
        if hook:
            p_logs = persona.apply_modifiers_for(hook, state)
            run_log.extend(p_logs)

        # persona post-choice commentary
        post = persona.post_choice_text(state, node, choice)
        run_log.append(post)

        # capture butterfly logs
        if butterfly.logs:
            run_log.extend(butterfly.logs)
            butterfly.logs.clear()

    ending_text = engine.compute_ending_string()
    result = {
        "difficulty": difficulty,
        "persona": persona_id,
        "ending": ending_text,
        "final_stats": dict(state.stats),
        "final_flags": dict(state.flags),
        "inventory": list(state.inventory),
        "butterfly_log": run_log,
    }

    if verbose:
        print("\n--- Simulation verbose ---")
        print("Playstyle:", playstyle_sequence)
        print("Persona:", persona_id)
        print("Result:", ending_text)
        for line in run_log:
            print("  >", line)
        print(state.debug_summary())

    return result


def run_all_simulations_for_persona(persona_id: str):
    difficulties = ["easy", "medium", "hard"]
    results = {}
    for pname, seq in PLAYSTYLES.items():
        results[pname] = {}
        print("\n" + "=" * 72)
        print(f"Playstyle: {pname}")
        print("=" * 72)
        for d in difficulties:
            res = simulate_playstyle_with_persona(seq, d, persona_id, verbose=False)
            results[pname][d] = res
            print(f"- {d.title():6} -> {res['ending']}")
            sp = res["final_stats"]["system_points"]
            et = res["final_stats"]["ethan_hostility"]
            npres = res["final_stats"]["nicole_pressure"]
            print(f"    system_points={sp}, ethan_hostility={et}, nicole_pressure={npres}")
            if res["butterfly_log"]:
                print("    Persona/Butterfly log (excerpt):")
                for line in res["butterfly_log"][:5]:
                    print(f"      - {line}")
    return results


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", default="neutral", help="Persona id to use for narration (neutral, nicole, wendy, ethan)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    persona_id = args.persona
    if persona_id not in PERSONAS:
        print(f"Persona '{persona_id}' not found. Available: {', '.join(PERSONAS.keys())}")
        persona_id = "neutral"
    print(f"Running simulations with persona: {persona_id}\n")
    run_all_simulations_for_persona(persona_id)
