#! /usr/bin/env python3

import os
import sys
import argparse
import subprocess

if __name__ == "__main__":
  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')
  subparsers = parser.add_subparsers(help='sub-command help', dest='cmd')

  cwd = os.getcwd()

  parser_setup = subparsers.add_parser('setup', help='setup the de10 playground files')
  parser_setup.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS', default='template-parameters.yaml'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser_setup.add_argument(
    '--template-directory', metavar='TEMPLATE_DIRECTORY', default=f'{cwd}/templates'
  , help="The TEMPLATE_DIRECTORY containing the jinja templates")
  parser_setup.add_argument(
    '-d', '--output-directory', metavar='OUT_DIR', default=f'{cwd}/setup_output'
  , help='The OUT_PATH path to the output directory' )

  parser_run = subparsers.add_parser('run', help='run the de10 playground')
  parser_run.add_argument('setup_directory', metavar='SETUP_DIR'
  , default='./setup_output'
  , help='The OUT_PATH path to the output directory' )

  # parse command line arguments
  #clargs=parser.parse_args()
  clargs, rest = parser.parse_known_args()

  if not clargs.cmd:
    sys.stderr.write('\n')
    sys.stderr.write('/!\\ No command was specified /!\\\n')
    sys.stderr.write('\n')
    parser.print_help()
    sys.exit(2)

  if clargs.cmd == 'setup':
    from doit.cmd_base import ModuleTaskLoader
    from doit.doit_cmd import DoitMain
    import de10pro_playground_setup_doit_tasks
    de10pro_playground_setup_doit_tasks.init_ctxt(
      template_parameters=clargs.template_parameters
    , template_directory=clargs.template_directory
    , output_directory=clargs.output_directory
    )
    sys.exit(DoitMain(ModuleTaskLoader(de10pro_playground_setup_doit_tasks)).run(rest))

  if clargs.cmd == 'run':
    d = clargs.setup_directory
    if not os.path.isfile(f'{d}/de10pro-playground-user-vm.qcow2'):
      sys.stderr.write(f'no de10pro-playground-user-vm.qcow2 found in {d}\n')
      sys.exit(1)

    cmd = [ '/opt/de10playground/bin/de10playground'
          , f'{clargs.setup_directory}/de10pro-playground-user-vm.qcow2' ]
    if os.path.isfile(f'{d}/de10playground_payload.img'):
      cmd.append(f'{clargs.setup_directory}/de10playground_payload.img')
    subprocess.run(cmd)
