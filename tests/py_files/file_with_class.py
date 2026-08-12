# A class body is a code object nested in the module, and its methods are
# nested once more, so this checks that deobfuscation recurses correctly.
import time

time.sleep(2)


class Container:
    def __init__(self, value):
        self.constant = 4
        self.value = value


instance = Container(9)
has_expected_constant = instance.constant == 4
