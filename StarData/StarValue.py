from .Error import *
from typing import Optional
import uuid


class StarValue:
    def __init__(self, value_type: str, value):
        self.value_type = value_type
        self.value = value

    def return_helper(self, value_type: str, value):
        if self.value_type == value_type:
            return value
        else:
            raise StarTypeError(f"The type you should choose is {self.value_type}")

    def uuid(self) -> Optional[uuid.UUID]:
        if self.value is None:
            return None
        return self.return_helper('uuid', uuid.UUID("{" + str(self.value) + "}"))

    def str(self) -> Optional[str]:
        if self.value is None:
            return None
        return self.return_helper('str', str(self.value))


class StarEmpty:
    pass
