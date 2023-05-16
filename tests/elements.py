from drawable import DrawableElement

import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s:%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Sample(DrawableElement):
    """Just simple body without children."""

    param_int_123: int
    param_str_abc: str

    def _draw(self, body=None, **kwargs) -> None:
        logger.info("sample param_int_123 %d", self.param_int_123)
        logger.info("sample param_str_abc %s", self.param_str_abc)


class Parent(DrawableElement):
    """Simple parent of Sample."""

    sample1: Sample
    param_int_123: int
    param_int_parent: int

    def _draw(self, body=None, **kwargs) -> None:
        logger.info("parent param_int_123 %d", self.param_int_123)
        logger.info("parent param_int_parent %d", self.param_int_parent)
        self.sample1.draw(body)
