import unittest
from unittest.mock import patch

import pytest

import langsmith.utils as ls_utils
from langsmith.run_helpers import tracing_context


class LangSmithProjectNameTest(unittest.TestCase):
    class GetTracerProjectTestCase:
        def __init__(
            self, test_name, envvars, expected_project_name, return_default_value=None
        ):
            self.test_name = test_name
            self.envvars = envvars
            self.expected_project_name = expected_project_name
            self.return_default_value = return_default_value

    def test_correct_get_tracer_project(self):
        cases = [
            self.GetTracerProjectTestCase(
                test_name="default to 'default' when no project provided",
                envvars={},
                expected_project_name="default",
            ),
            self.GetTracerProjectTestCase(
                test_name="default to 'default' when "
                + "return_default_value=True and no project provided",
                envvars={},
                expected_project_name="default",
            ),
            self.GetTracerProjectTestCase(
                test_name="do not default if return_default_value=False "
                + "when no project provided",
                envvars={},
                expected_project_name=None,
                return_default_value=False,
            ),
            self.GetTracerProjectTestCase(
                test_name="use session_name for legacy tracers",
                envvars={"LANGCHAIN_SESSION": "old_timey_session"},
                expected_project_name="old_timey_session",
            ),
            self.GetTracerProjectTestCase(
                test_name="use LANGCHAIN_PROJECT over SESSION_NAME",
                envvars={
                    "LANGCHAIN_SESSION": "old_timey_session",
                    "LANGCHAIN_PROJECT": "modern_session",
                },
                expected_project_name="modern_session",
            ),
            self.GetTracerProjectTestCase(
                test_name="hosted projects get precedence over all other defaults",
                envvars={
                    "HOSTED_LANGSERVE_PROJECT_NAME": "hosted_project",
                    "LANGCHAIN_SESSION": "old_timey_session",
                    "LANGCHAIN_PROJECT": "modern_session",
                },
                expected_project_name="hosted_project",
            ),
        ]

        for case in cases:
            with self.subTest(msg=case.test_name):
                with pytest.MonkeyPatch.context() as mp:
                    for k, v in case.envvars.items():
                        mp.setenv(k, v)

                    project = (
                        ls_utils.get_tracer_project()
                        if case.return_default_value is None
                        else ls_utils.get_tracer_project(case.return_default_value)
                    )
                    self.assertEqual(project, case.expected_project_name)


def test_tracing_enabled():
    with patch.dict("os.environ", {"LANGCHAIN_TRACING": "false"}):
        assert not ls_utils.tracing_is_enabled()
        with tracing_context(enabled=True):
            assert ls_utils.tracing_is_enabled()
        assert not ls_utils.tracing_is_enabled()
