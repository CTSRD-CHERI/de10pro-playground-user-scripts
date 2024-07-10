#! /usr/bin/env python3

import sys
import argparse

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

if __name__ == "__main__":
  # command line arguments
  parser = argparse.ArgumentParser(description='setup de10pro playground files')

  # general, common options
  parser.add_argument(
    '--template-parameters', metavar='YAML_TEMPLATE_PARAMETERS', default='template-parameters.yaml'
  , help="The YAML_TEMPLATE_PARAMETERS yaml file with the jinja template parameters to use")
  parser.add_argument(
    '--template-directory', metavar='TEMPLATE_DIRECTORY', default='./templates'
  , help="The TEMPLATE_DIRECTORY containing the jinja templates")
  parser.add_argument(
    '-d', '--output-directory', metavar='OUT_DIR', default='./setup_output'
  , help='The OUT_PATH path to the output directory' )

  # parse command line arguments
  #clargs=parser.parse_args()
  clargs, rest = parser.parse_known_args()
  import de10pro_playground_setup_doit_tasks
  de10pro_playground_setup_doit_tasks.init_ctxt(**vars(clargs))
  sys.exit(DoitMain(ModuleTaskLoader(de10pro_playground_setup_doit_tasks)).run(rest))
