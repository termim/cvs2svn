# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2000-2006 CollabNet.  All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.  The terms
# are also available at http://subversion.tigris.org/license-1.html.
# If newer versions of this license are posted there, you may use a
# newer version instead, at your option.
#
# This software consists of voluntary contributions made by many
# individuals.  For exact contribution history, see the revision
# history and logs, available at http://cvs2svn.tigris.org/.
# ====================================================================

"""This module contains tools to manage the passes of a conversion."""


import time

from boolean import *
import config
from context import Ctx
from log import Log
from stats_keeper import StatsKeeper
from artifact_manager import artifact_manager


class PassManager:
  """Manage a list of passes that can be executed separately or all at once.

  Passes are numbered starting with 1."""

  def __init__(self, passes):
    """Construct a PassManager with the specified PASSES.

    Internally, passes are numbered starting with 1.  So PASSES[0] is
    considered to be pass number 1."""

    self.passes = passes
    self.num_passes = len(self.passes)

  def run(self, start_pass, end_pass):
    """Run the specified passes, one after another.

    START_PASS is the number of the first pass that should be run.
    END_PASS is the number of the last pass that should be run.  It
    must be that 1 <= START_PASS <= END_PASS <= self.num_passes."""

    artifact_manager.register_temp_file(config.STATISTICS_FILE, self)

    StatsKeeper().set_start_time(time.time())

    # Inform the artifact manager when artifacts are created and used:
    for the_pass in self.passes:
      # The statistics object is needed for every pass:
      artifact_manager.register_temp_file_needed(
          config.STATISTICS_FILE, the_pass)
      the_pass.register_artifacts()

    # Tell the artifact manager about passes that are being skipped this run:
    for the_pass in self.passes[0:start_pass - 1]:
      artifact_manager.pass_skipped(the_pass)

    times = [ None ] * (end_pass + 1)
    times[start_pass - 1] = time.time()
    for i in range(start_pass - 1, end_pass):
      the_pass = self.passes[i]
      Log().write(Log.QUIET,
                  '----- pass %d (%s) -----' % (i + 1, the_pass.name,))
      the_pass.run()
      times[i + 1] = time.time()
      StatsKeeper().log_duration_for_pass(times[i + 1] - times[i], i + 1)
      # Dispose of items in Ctx() not intended to live past the end of the pass
      # (Identified by exactly one leading underscore)
      for attr in dir(Ctx()):
        if (len(attr) > 2 and attr[0] == '_' and attr[1] != '_'
            and attr[:6] != "_Ctx__"):
          delattr(Ctx(), attr)
      StatsKeeper().set_end_time(time.time())
      # Allow the artifact manager to clean up artifacts that are no
      # longer needed:
      artifact_manager.pass_done(the_pass)

    # Tell the artifact manager about passes that are being deferred:
    for the_pass in self.passes[end_pass:]:
      artifact_manager.pass_deferred(the_pass)

    Log().write(Log.QUIET, StatsKeeper())
    Log().write(Log.NORMAL, StatsKeeper().timings())

    # The overall conversion is done:
    artifact_manager.pass_done(self)

    # Consistency check:
    artifact_manager.check_clean()

  def help_passes(self):
    """Output (to sys.stdout) the indices and names of available passes."""

    print 'PASSES:'
    for i in range(len(self.passes)):
      print '%5d : %s' % (i + 1, self.passes[i].name,)

