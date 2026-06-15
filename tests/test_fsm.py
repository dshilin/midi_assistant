import pytest
from app.state import get_state, update_state, reset_state, STATE
from app.fsm import next_stage
from app.prompts import build_system_prompt


class TestState:
    def test_get_default_state(self):
        state = get_state("unknown_user")
        assert state["stage"] == "discovery"
        assert state["type"] is None
        assert state["color"] is None
        assert state["area"] is None

    def test_update_state(self):
        state = update_state("user1", {"type": "ламинат", "color": "дуб"})
        assert state["type"] == "ламинат"
        assert state["color"] == "дуб"
        assert state["stage"] == "discovery"

    def test_update_state_with_stage(self):
        state = update_state("user1", {}, stage="selection")
        assert state["stage"] == "selection"

    def test_update_state_ignores_none(self):
        update_state("user2", {"type": "ламинат"})
        update_state("user2", {"type": None, "color": "белый"})
        state = get_state("user2")
        assert state["type"] == "ламинат"
        assert state["color"] == "белый"

    def test_reset_state(self):
        update_state("user3", {"type": "ламинат", "stage": "closing"})
        state = reset_state("user3")
        assert state["type"] is None
        assert state["stage"] == "discovery"

    def test_state_isolation(self):
        reset_state("iso_a")
        reset_state("iso_b")
        update_state("iso_a", {"type": "ламинат"})
        assert get_state("iso_b")["type"] is None


class TestFSM:
    def test_discovery_to_selection_on_type(self):
        state = {"stage": "discovery", "type": "ламинат", "color": None}
        assert next_stage(state) == "selection"

    def test_discovery_to_selection_on_color(self):
        state = {"stage": "discovery", "type": None, "color": "белый"}
        assert next_stage(state) == "selection"

    def test_discovery_stays_if_no_data(self):
        state = {"stage": "discovery", "type": None, "color": None}
        assert next_stage(state) == "discovery"

    def test_selection_to_calculation(self):
        state = {"stage": "selection", "selected_product": 1}
        assert next_stage(state) == "calculation"

    def test_selection_stays_without_product(self):
        state = {"stage": "selection", "selected_product": None}
        assert next_stage(state) == "selection"

    def test_calculation_to_closing(self):
        state = {"stage": "calculation"}
        assert next_stage(state) == "closing"

    def test_closing_stays_closing(self):
        state = {"stage": "closing"}
        assert next_stage(state) == "closing"


class TestPrompts:
    def test_build_system_prompt(self):
        state = {"stage": "discovery", "type": None, "color": None, "area": None, "brand": None, "room_type": None}
        prompt = build_system_prompt(state)
        assert "discovery" in prompt
        assert "AI-консультант" in prompt
        assert "get_products" in prompt

    def test_prompt_changes_by_stage(self):
        discovery_state = {"stage": "discovery", "type": None, "color": None, "area": None, "brand": None, "room_type": None}
        selection_state = {"stage": "selection", "type": "ламинат", "color": "дуб", "area": 20, "brand": None, "room_type": "гостиная"}

        discovery_prompt = build_system_prompt(discovery_state)
        selection_prompt = build_system_prompt(selection_state)

        assert "Задавай вопросы" in discovery_prompt
        assert "get_products" in selection_prompt
