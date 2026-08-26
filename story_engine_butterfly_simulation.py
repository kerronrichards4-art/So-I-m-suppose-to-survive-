#!/usr/bin/env python3
"""
story_engine_butterfly_simulation.py

Simulation harness with a deterministic Butterfly Effect system that alters
branch availability and outcome checks based on prior choices and stats.

Run:
    python3 story_engine_butterfly_simulation.py
"""

from typing import Dict, List, Tuple, Callable


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
    Rule-based deterministic butterfly effect engine.

    Each rule examines the current StoryState and the node about to be played,
    and may:
      - Modify stats or flags (cumulative side-effects)
      - Alter choice availability (disable choices by index)
      - Adjust "outcome_modifiers" used by choice effects

    The rules are deterministic, auditable, and run in fixed order.
    """

    def __init__(self):
        self.logs: List[str] = []
        # outcome_modifiers can be read by choice effect functions
        self.outcome_modifiers: Dict[str, int] = {}

    def reset(self):
        self.logs.clear()
        self.outcome_modifiers.clear()

    def apply_rules_before_node(self, node: NarrativeNode, state: StoryState) -> List[int]:
        """
        Return a list of indices of choices that are disabled by butterfly rules.
        If empty list, no choices disabled.
        """
        disabled_indices: List[int] = []
        # Clear per-node modifiers
        self.outcome_modifiers.clear()

        # Rule A: If you refused Nicole and nicole_pressure >= 50,
        # legal sabotage begins -- reduce system points later at gala.
        if not state.flags.get("engaged_to_nicole") and state.stats["nicole_pressure"] >= 50:
            if not state.flags.get("legal_sabotage"):
                state.set_flag("legal_sabotage", True)
                self.logs.append("Rule A fired: Legal sabotage activated (nicole_pressure high & not engaged).")

        # Rule B: If ethan_hostility is very high, prepare an ambush: direct fight becomes disabled
        if state.stats["ethan_hostility"] >= 80:
            # find index of direct fight in node. If present, disable it.
            for idx, ch in enumerate(node.choices):
                if "direct" in ch["text"].lower() or "confront" in ch["text"].lower():
                    disabled_indices.append(idx)
                    self.logs.append(f"Rule B fired: Direct confrontation disabled on node '{node.node_id}' due to Ethan hostility.")
                    # also set an ambush flag that may reduce system_points later
                    if not state.flags.get("ethan_ambush_ready"):
                        state.set_flag("ethan_ambush_ready", True)
                        self.logs.append("  - Ethan ambush flag set.")

        # Rule C: Saving heroines increases female-lead political scrutiny (but also gives plot leverage)
        if state.flags.get("saved_heroines"):
            # increase nicole_pressure gradually if Nicole is insecure
            if state.stats["nicole_trust"] < 40:
                state.modify_stat("nicole_pressure", +5)
                self.logs.append("Rule C: Saving heroines increased Nicole pressure due to jealousy.")
            # Give auction advantage modifier because heroines can influence bidders
            self.outcome_modifiers["auction_influence"] = 10
            self.logs.append("Rule C: Saving heroines grants auction influence +10.")

        # Rule D: Legal sabotage reduces effective system points at Gala
        if state.flags.get("legal_sabotage"):
            self.outcome_modifiers["legal_sabotage_penalty"] = -20
            self.logs.append("Rule D: Legal sabotage will apply -20 to system points at Gala outcome check.")

        # Rule E: Nicole pressure very high reduces chances of public success (makes some choice outcomes harder)
        if state.stats["nicole_pressure"] >= 75:
            self.outcome_modifiers["nicole_pressure_penalty"] = -15
            self.logs.append("Rule E: Nicole pressure penalty active (-15 to relevant checks).")

        return disabled_indices

    def apply_rules_before_outcome(self, node_id: str, state: StoryState, base_success: bool, context: str = "") -> bool:
        """
        Given a base success computed by the effect logic, adjust success deterministically
        using accumulated outcome_modifiers and state. Returns final success boolean.
        """
        score = 0
        # translate base_success into starting score
        score += 100 if base_success else 0

        # Apply auction_influence
        score += self.outcome_modifiers.get("auction_influence", 0)
        # Apply legal sabotage penalty
        score += self.outcome_modifiers.get("legal_sabotage_penalty", 0)
        # Apply nicole pressure penalty
        score += self.outcome_modifiers.get("nicole_pressure_penalty", 0)

        # Tie to system_points proportionally (normalized)
        score += int((state.stats["system_points"] - 50) / 1.5)  # some scaling

        # If Ethan ambush is ready and context is 'gala', cut a big penalty
        if state.flags.get("ethan_ambush_ready") and node_id == "act3_gala":
            score -= 40
            self.logs.append("Rule: Ethan ambush penalized gala outcome (-40).")

        # deterministically decide final success threshold
        final_success = score >= 80  # fixed threshold
        self.logs.append(f"Outcome calc for {context or node_id}: base={base_success}, score={score} -> {'SUCCESS' if final_success else 'FAIL'}")
        return final_success


class StoryEngine:
    def __init__(self, difficulty: str = "medium"):
        self.state = StoryState(difficulty)
        self.nodes: Dict[str, NarrativeNode] = {}
        self.butterfly = ButterflyEffectSystem()

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
# Effects used by choices (now consult butterfly system)
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
    # base success logic (as before)
    if state.difficulty == "hard":
        base_success = state.flags["engaged_to_nicole"] and state.stats["system_points"] >= 100
    else:
        base_success = state.flags["engaged_to_nicole"] or state.stats["system_points"] >= 80

    # Apply butterfly outcome modifiers deterministically
    final_success = butterfly.apply_rules_before_outcome("act3_gala", state, base_success, context="auction")
    state.set_flag("ethan_bankrupted", final_success)


def direct_fight_effect(state: StoryState, butterfly: ButterflyEffectSystem):
    # base success requires the defense card
    base_success = "Absolute Defense Card" in state.inventory
    # Butterfly may alter the outcome (ambush, pressure penalties)
    final_success = butterfly.apply_rules_before_outcome("act3_gala", state, base_success, context="direct_fight")
    state.set_flag("ethan_bankrupted", final_success)


# --------------------------
# Build sample engine nodes
# --------------------------
def build_sample_engine(difficulty: str = "medium") -> StoryEngine:
    engine = StoryEngine(difficulty=difficulty)

    engine.add_node(NarrativeNode(
        "act1_morning",
        "You wake up next to Nicole Rivers. She demands an immediate public engagement announcement.",
        [
            {"text": "Accept the engagement.", "next_node": "act2_heroines", "effect": accept_engagement_effect},
            {"text": "Refuse and try to escape her family influence.", "next_node": "act2_heroines", "effect": refuse_engagement_effect}
        ]
    ))

    engine.add_node(NarrativeNode(
        "act2_heroines",
        "You spot Wendy Taylor and Jessica Snow trapped in a dangerous situation. Ethan Knight is en route to rescue them.",
        [
            {"text": "Intervene using System Martial Arts to rescue them first.", "next_node": "act3_gala", "effect": save_heroines_effect},
            {"text": "Ignore them and let Ethan Knight take the spotlight.", "next_node": "act3_gala", "effect": ignore_heroines_effect}
        ]
    ))

    engine.add_node(NarrativeNode(
        "act3_gala",
        "At the Investment Gala, Ethan Knight makes his play for absolute power.",
        [
            # Note: effect functions here expect the butterfly system, so new simulation will call them accordingly
            {"text": "Dress as a 'clown' and disrupt the auction.", "next_node": "ending", "effect": auction_clown_effect},
            {"text": "Confront Ethan directly in martial combat.", "next_node": "ending", "effect": direct_fight_effect}
        ]
    ))

    engine.add_node(NarrativeNode("ending", "", []))
    return engine


# --------------------------
# Playstyles described as sequence of (node_id, choice_index)
# --------------------------
PLAYSTYLES: Dict[str, List[Tuple[str, int]]] = {
    # Accept Nicole -> Intervene -> Clown
    "Shadow Strategist": [("act1_morning", 0), ("act2_heroines", 0), ("act3_gala", 0)],
    # Accept Nicole -> Ignore Heroines -> Clown
    "Puppet of the Ice Queen": [("act1_morning", 0), ("act2_heroines", 1), ("act3_gala", 0)],
    # Refuse Nicole -> Ignore Heroines -> Direct Fight
    "Erased by the Plot": [("act1_morning", 1), ("act2_heroines", 1), ("act3_gala", 1)],
    # Refuse Nicole -> Intervene -> Direct Fight
    "Solitary Rogue": [("act1_morning", 1), ("act2_heroines", 0), ("act3_gala", 1)],
}


def simulate_playstyle_with_butterfly(playstyle_sequence: List[Tuple[str, int]], difficulty: str, verbose: bool = False) -> Dict:
    engine = build_sample_engine(difficulty)
    state = engine.state
    butterfly = engine.butterfly

    # Keep an ordered log of butterfly events for traceability
    run_log: List[str] = []
    butterfly.reset()

    for node_id, choice_idx in playstyle_sequence:
        # start of scene: apply per-turn decay
        state.apply_turn_decay()
        node = engine.nodes.get(node_id)
        if not node:
            run_log.append(f"Node {node_id} not found; stopping.")
            break

        # Let butterfly examine the node and state; it may disable choices
        disabled = butterfly.apply_rules_before_node(node, state)
        if disabled:
            run_log.append(f"Butterfly disabled choices at {node_id}: {disabled}")

        # Validate requested choice: if disabled, we treat it as a forced fallback (choose first enabled)
        if choice_idx in disabled:
            run_log.append(f"Requested choice {choice_idx} at {node_id} was disabled by butterfly rules.")
            # find a fallback: pick first enabled choice index (or None)
            enabled_indices = [i for i in range(len(node.choices)) if i not in disabled]
            if not enabled_indices:
                run_log.append(f"No choices available at {node_id} after butterfly rules; stopping.")
                break
            fallback_idx = enabled_indices[0]
            run_log.append(f"Falling back to choice {fallback_idx} instead.")
            choice_idx = fallback_idx

        choice = node.choices[choice_idx]
        # Execute effect. Effects that need butterfly will accept it as an argument.
        eff = choice.get("effect")
        if eff:
            # If effect expects butterfly, call with both
            try:
                eff(state, butterfly)  # type: ignore
            except TypeError:
                # effect doesn't accept butterfly -> call normally
                eff(state)  # type: ignore

        # after effect, capture any butterfly logs
        if butterfly.logs:
            run_log.extend(butterfly.logs)
            butterfly.logs.clear()

    # After all choices, compute final ending
    ending_text = engine.compute_ending_string()
    result = {
        "difficulty": difficulty,
        "ending": ending_text,
        "final_stats": dict(state.stats),
        "final_flags": dict(state.flags),
        "inventory": list(state.inventory),
        "butterfly_log": run_log,
    }

    if verbose:
        print("\n--- Simulation verbose ---")
        print("Playstyle:", playstyle_sequence)
        print("Result:", ending_text)
        for line in run_log:
            print("  >", line)
        print(state.debug_summary())

    return result


def run_all_simulations_verbose():
    difficulties = ["easy", "medium", "hard"]
    results = {}
    for pname, seq in PLAYSTYLES.items():
        results[pname] = {}
        print("\n" + "=" * 72)
        print(f"Playstyle: {pname}")
        print("=" * 72)
        for d in difficulties:
            res = simulate_playstyle_with_butterfly(seq, d, verbose=False)
            results[pname][d] = res
            print(f"- {d.title():6} -> {res['ending']}")
            sp = res["final_stats"]["system_points"]
            et = res["final_stats"]["ethan_hostility"]
            npres = res["final_stats"]["nicole_pressure"]
            flags = res["final_flags"]
            print(f"    system_points={sp}, ethan_hostility={et}, nicole_pressure={npres}")
            # show which butterfly rules fired (short)
            if res["butterfly_log"]:
                print("    Butterfly log:")
                for line in res["butterfly_log"]:
                    print(f"      - {line}")
    return results


if __name__ == "__main__":
    print("Running gated simulations with Butterfly Effect system enabled...")
    run_all_simulations_verbose()
    print("\nDone.")
