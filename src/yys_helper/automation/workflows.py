from __future__ import annotations

from yys_helper.domain.models import StopReason

from .engine import Transition, Workflow


COMMON_STOPS = {
    "stamina_empty": StopReason.INSUFFICIENT_STAMINA,
    "network_error": StopReason.NETWORK_ERROR,
    "inventory_full": StopReason.INVENTORY_FULL,
    "login": StopReason.NETWORK_ERROR,
}


def chapter_28_workflow() -> Workflow:
    return Workflow(
        name="困28循环",
        transitions={
            "home": Transition("open_explore", ("chapter_select",)),
            "chapter_select": Transition("select_chapter_28_hard", ("explore_map",)),
            "explore_map": Transition("tap_monster", ("battle",)),
            "battle": Transition("wait_battle", ("settlement",)),
            "settlement": Transition("confirm", ("explore_map",), round_completed=True),
        },
        stop_scenes=dict(COMMON_STOPS),
    )


def soul_dungeon_workflow() -> Workflow:
    return Workflow(
        name="御魂副本循环",
        transitions={
            "home": Transition("open_soul_dungeon", ("soul_ready",)),
            "soul_ready": Transition("start_battle", ("battle",)),
            "battle": Transition("wait_battle", ("settlement",)),
            "settlement": Transition(
                "challenge_again", ("soul_ready",), round_completed=True
            ),
        },
        stop_scenes=dict(COMMON_STOPS),
    )
