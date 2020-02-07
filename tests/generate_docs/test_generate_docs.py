import pathlib
from subprocess import CalledProcessError
from unittest import mock, TestCase

from pyfakefs.fake_filesystem_unittest import Patcher

from mbed_tools_ci_scripts.generate_docs import (
    _clear_previous_docs,
    _generate_pdoc_command_list,
    generate_documentation,
    generate_docs,
)


class TestGenerateDocs(TestCase):
    def test_clear_previous_docs(self):
        with Patcher() as patcher:
            fake_output_dir = pathlib.Path("local_docs")
            patcher.fs.create_file(
                str(fake_output_dir.joinpath("some_docs_file.html")), contents="This is some old documentation.",
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
    @mock.patch("mbed_tools_ci_scripts.generate_docs.TemporaryDirectory")
    def test_generate_docs(self, TemporaryDirectory, check_call, _clear_previous_docs):
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"
        with Patcher():
            temp_dir = pathlib.Path("temp")
            TemporaryDirectory.return_value.__enter__.return_value = temp_dir
            result = generate_docs(fake_output_dir, fake_module)

            self.assertEqual(result, 0)
            _clear_previous_docs.assert_called_once_with(fake_output_dir)
            check_call.assert_called_once_with(_generate_pdoc_command_list(temp_dir, fake_module))

    @mock.patch("mbed_tools_ci_scripts.generate_docs._clear_previous_docs")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.log_exception")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.check_call")
    @mock.patch("mbed_tools_ci_scripts.generate_docs.TemporaryDirectory")
    def test_generate_docs_errors(self, TemporaryDirectory, check_call, log_exception, _clear_previous_docs):
        check_call.side_effect = CalledProcessError(returncode=2, cmd=["pdoc", "some", "stuff"])
        fake_output_dir = pathlib.Path("fake/docs")
        fake_module = "module"
        with Patcher():
            temp_dir = pathlib.Path("temp")
            TemporaryDirectory.return_value = temp_dir

            result = generate_docs(fake_output_dir, fake_module)

            self.assertEqual(result, 1)
            _clear_previous_docs.assert_called_once_with(fake_output_dir)
            check_call.assert_called_once_with(_generate_pdoc_command_list(temp_dir, fake_module))
            log_exception.assert_called_once()

    @mock.patch("mbed_tools_ci_scripts.generate_docs.TemporaryDirectory")
    @mock.patch("mbed_tools_ci_scripts.generate_docs._call_pdoc")
    def test_update_docs(self, _call_pdoc, TemporaryDictionary):
        with Patcher() as patcher:
            temp_dir = pathlib.Path("temp")
            TemporaryDictionary.return_value = temp_dir

            module_name = "module_name"
            docs_dir = pathlib.Path("docs")

            def mocked_pdoc(output_directory, module):
                # Creating some fake files in a same way as Pdoc
                if not output_directory.exists():
                    patcher.fs.create_dir(output_directory)
                docs_contents_dir = output_directory.joinpath(module)
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("docs_file.html")), contents="This is some documentation."
                )
                # check that it moves subdirectories too
                patcher.fs.create_file(
                    str(docs_contents_dir.joinpath("sub_dir", "docs_file.html")),
                    contents="This is some more documentation.",
                )

            _call_pdoc.side_effect = mocked_pdoc

            patcher.fs.create_file(
                str(docs_dir.joinpath("old_docs_file.html")), contents="This is some old documentation."
            )
            self.assertTrue(docs_dir.joinpath("old_docs_file.html").exists())

            generate_documentation(docs_dir, module_name)

            _call_pdoc.assert_called_once_with(temp_dir, module_name)

            # Check that old documentation in the output directory has been removed
            self.assertFalse(docs_dir.joinpath("old_docs_file.html").exists())
            # Check that module name directory is not present in the output directory
            self.assertTrue(docs_dir.joinpath("docs_file.html").is_file())
            self.assertTrue(docs_dir.joinpath("sub_dir", "docs_file.html").is_file())
            self.assertFalse(docs_dir.joinpath(module_name).exists())
