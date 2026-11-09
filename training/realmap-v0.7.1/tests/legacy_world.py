"""Explicit pre-direct-delivery rules for historical recruitment regression tests."""
from aiwar.engine import World as CurrentWorld
class LegacyWorld(CurrentWorld):
    def __init__(self,seed=1,config=None):
        super().__init__(seed,dict(config or {},direct_garrison_delivery=False))
