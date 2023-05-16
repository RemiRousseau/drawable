
import unittest
from . import elements


class BasicTest(unittest.TestCase):
    """Test utils format function."""

    chip = None

    def draw(self):
        with self.assertLogs(elements.logger) as captured:
            self.chip.draw(body=None)  # type: ignore
        return captured.records

    def check_logs(self, logs, msg, level):
        for log in logs:
            if msg in log.message and log.levelno >= level:
                return True
        return False

    def assert_logs(
            self, logs, msg=None, level=None):
        if isinstance(msg, list):
            for msg_ in msg:
                self.assert_logs(logs, msg_, level)
            return

        if msg:
            level = level if level is not None else 10
            self.assertTrue(self.check_logs(logs, msg, level),
                            msg=f"No '{msg}' at level {level} inside: {logs}")
            return

        msg = "External variable used"
        level = level or 0
        self.assertFalse(
            self.check_logs(logs, msg, level),
            msg=f"There is '{msg}' inside: {[f'{log.levelno}:{log.message}' for log in logs]}")

    def test_sample(self):
        self.chip = elements.Sample(
            folder="tests/yaml_files",
            params="sample.yaml",
            modeler=None,
            name="chip"
        )
        logs = self.draw()
        self.assert_logs(logs,
                         ['sample param_int_123 123',
                          'sample param_str_abc abc'])

    def test_parent(self):
        self.chip = elements.Parent(
            folder="tests/yaml_files",
            params="parent.yaml",
            modeler=None,
            name="chip"
        )
        logs = self.draw()
        self.assert_logs(logs,
                         ['sample param_int_123 123',
                          'sample param_str_abc abc',
                          'parent param_int_123 456',
                          'parent param_int_parent 789'])

    def test_parent_link(self):
        self.chip = elements.Parent(
            folder="tests/yaml_files",
            params="parent_link.yaml",
            modeler=None,
            name="chip"
        )
        logs = self.draw()
        self.assert_logs(logs,
                         ['sample param_int_123 123',
                          'sample param_str_abc abc',
                          'parent param_int_123 456',
                          'parent param_int_parent 789'])


if __name__ == '__main__':
    unittest.main()
