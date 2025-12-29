import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Hello, world!")


class SomeClass:
    @property
    def some_prop(self):
        return 10

obj = SomeClass()
print(obj.some_prop)