import pathlib
from subprocess import CalledProcessError
from unittest import mock, TestCase

from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci_scripts.generate_docs import (
    _clear_previous_docs,
    _generate_pdoc_command_list,
    generate_docs,
)


class TestGenerateDocs(TestCase):
    def test_clear_previous_docs(self):
        with Patcher() as patcher:
            fake_output_dir = pathlib.Path("local_docs")
            patcher.fs.create_file(
                str(fake_output_dir.joinpath("some_docs_file.html")),
                contents="This is some old documentation.",
            )
            self.assertTrue(fake_output_dir.is_dir())

            _clear_previous_docs(fake_output_dir)
            self.assertFalse(fake_output_dir.is_dir())

    def test_clear_previous_docs_none_exist(self):
        fake_output_dir = pathlib.Path("local_docs")
        self.assertFalse(fake_output_dir.is_dir())

        _clear_previous_docs(fake_output_dir)

    @mock.patch("mbed_tools_ci_scripts.generate_docs._clear_previous_docs")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.check_call")
    def test_generate_docs(self, check_call, _clear_previous_docs):
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"

        result = generate_docs(fake_output_dir, fake_module)

        self.assertEqual(result, 0)
        _clear_previous_docs.assert_called_once_with(fake_output_dir)
        check_call.assert_called_once_with(
            _generate_pdoc_command_list(fake_output_dir, fake_module)
        )

    @mock.patch("mbed_tools_ci_scripts.generate_docs._clear_previous_docs")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.log_exception")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.check_call")
    def test_generate_docs_errors(self, check_call, log_exception, _clear_previous_docs):
        check_call.side_effect = CalledProcessError(
            returncode=2, cmd=["pdoc", "some", "stuff"]
        )
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"

        result = generate_docs(fake_output_dir, fake_module)

        self.assertEqual(result, 1)
        _clear_previous_docs.assert_called_once_with(fake_output_dir)
        check_call.assert_called_once_with(
            _generate_pdoc_command_list(fake_output_dir, fake_module)
        )
        log_exception.assert_called_once()
