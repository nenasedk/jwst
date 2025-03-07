from os.path import (
    abspath,
    dirname,
    join,
)

import pytest

from jwst import datamodels
from jwst.stpipe import Step
from jwst.stpipe.config_parser import ValidationError


def test_hook():
    """Test the running of hooks"""
    step_fn = join(dirname(__file__), 'steps', 'stepwithmodel_hook.cfg')
    step = Step.from_config_file(step_fn)

    model = datamodels.ImageModel()
    result = step.run(model)

    assert result.pre_hook_run
    assert step.pre_hook_run
    assert result.post_hook_run
    assert step.post_hook_run


def test_hook_with_return():
    """Test the running of hooks"""
    step_fn = join(dirname(__file__), 'steps', 'stepwithmodel_hookreturn.cfg')
    step = Step.from_config_file(step_fn)

    model = datamodels.ImageModel()
    result = step.run(model)

    assert result == 'PostHookWithReturnStep executed'
    assert step.pre_hook_run
    assert step.post_hook_run


def test_step():
    step_fn = join(dirname(__file__), 'steps', 'some_other_step.cfg')
    step = Step.from_config_file(step_fn)

    from .steps import AnotherDummyStep

    assert isinstance(step, AnotherDummyStep)
    assert step.name == 'SomeOtherStepOriginal'
    assert step.par2 == 'abc def'

    step.run(1, 2)


def test_step_from_python():
    from .steps import AnotherDummyStep

    step = AnotherDummyStep("SomeOtherStepOriginal", par1=42.0, par2="abc def")

    assert step.par1 == 42.0
    assert step.par2 == 'abc def'
    assert step.par3 is False

    result = step.run(1, 2)

    assert result == 3


def test_step_from_python_simple():
    from .steps import AnotherDummyStep

    result = AnotherDummyStep.call(1, 2, par1=42.0, par2="abc def")

    assert result == 3


def test_step_from_python_simple2():
    from .steps import AnotherDummyStep

    step_fn = join(dirname(__file__), 'steps', 'some_other_step.cfg')

    result = AnotherDummyStep.call(1, 2, config_file=step_fn)

    assert result == 3



def test_step_from_commandline():
    args = [
        abspath(join(dirname(__file__), 'steps', 'some_other_step.cfg')),
        '--par1=58', '--par2=hij klm'
        ]

    step = Step.from_cmdline(args)

    assert step.par1 == 58.
    assert step.par2 == 'hij klm'
    assert step.par3 is True

    step.run(1, 2)


def test_step_from_commandline_class():
    args = [
        'jwst.stpipe.tests.steps.AnotherDummyStep',
        '--par1=58', '--par2=hij klm'
        ]

    step = Step.from_cmdline(args)

    assert step.par1 == 58.
    assert step.par2 == 'hij klm'
    assert step.par3 is False

    step.run(1, 2)


def test_step_from_commandline_invalid():
    args = [
            '__foo__'
        ]

    with pytest.raises(ValueError):
        Step.from_cmdline(args)


def test_step_from_commandline_invalid2():
    args = [
        '__foo__.__bar__'
        ]
    with pytest.raises(ValueError):
        Step.from_cmdline(args)


def test_step_from_commandline_invalid3():
    args = [
        'sys.foo'
        ]
    with pytest.raises(ValueError):
        Step.from_cmdline(args)


def test_step_from_commandline_invalid4():
    args = [
        'sys.argv'
        ]
    with pytest.raises(ValueError):
        Step.from_cmdline(args)


def test_step_with_local_class():
    step_fn = join(dirname(__file__), 'steps', 'local_class.cfg')
    step = Step.from_config_file(step_fn)

    step.run(datamodels.ImageModel((2, 2)))


def test_extra_parameter():
    from .steps import AnotherDummyStep
    with pytest.raises(ValidationError):
        AnotherDummyStep("SomeOtherStepOriginal", par5='foo')


def test_crds_override():
    from .steps import AnotherDummyStep

    step = AnotherDummyStep(
        "SomeOtherStepOriginal",
        par1=42.0, par2="abc def",
        override_flat_field=join(dirname(__file__), 'data', 'flat.fits'))

    fd = step.get_reference_file(datamodels.open(), 'flat_field')
    assert fd == join(dirname(__file__), 'data', 'flat.fits')


def test_omit_ref_file():
    from .steps import OptionalRefTypeStep

    step = OptionalRefTypeStep(override_to_be_ignored_ref_type="")
    step.process()


def test_search_attr():
    from .steps import SavePipeline

    value = '/tmp'
    pipeline = SavePipeline('afile.fits', output_dir=value)

    assert pipeline.search_attr('output_dir') == value
    assert pipeline.stepwithmodel.search_attr('output_dir') == value
    assert pipeline.search_attr('junk') is None
    assert pipeline.stepwithmodel.search_attr('junk') is None


def test_print_configspec():
    step = Step()
    step.print_configspec()
