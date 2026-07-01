from ampel.contrib.hu.t2 import HopskotchAdapter
from ampel.struct.UnitResult import UnitResult
from ampel.util.mappings import get_by_path


class ConditionalHopskotchAdapter(HopskotchAdapter):
    conditional_path: int | str | list[int | str]

    def handle(self, ur: UnitResult) -> UnitResult:
        assert isinstance(ur.body, dict)
        return super().handle(ur) if get_by_path(ur.body, self.conditional_path) else ur
