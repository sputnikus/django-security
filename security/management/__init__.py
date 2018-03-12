from argparse import ArgumentParser
from copy import copy

import django
from django.core.management import call_command as call_command_original
from django.core.management import execute_from_command_line as execute_from_command_line_original
from django.core.management import handle_default_options


def execute_from_command_line(argv=None):
    # some arguments must be processed before django setup
    parser = ArgumentParser()
    parser.add_argument('--settings')
    parser.add_argument('--pythonpath')
    options, args = parser.parse_known_args(argv[2:])
    handle_default_options(options)

    django.setup()

    from security.utils import CommandLogger
    return CommandLogger(
        command_function=lambda: execute_from_command_line_original(argv),
        command_name=argv[1],
        command_options=' '.join(argv[2:]),
        executed_from_command_line=True
    ).run()


def call_command(command_name, *args, **options):
    original_options = copy(options)
    stdout = options.pop('stdout')
    stderr = options.pop('stderr')

    from security.utils import CommandLogger
    return CommandLogger(
        command_function=lambda: call_command_original(command_name, *args, **options),
        stdout=stdout,
        stderr=stderr,
        command_name=command_name,
        command_options=', '.join(
            list(args)+['{}={}'.format(k, v) for k,v in original_options.items()]
        )
    ).run()
