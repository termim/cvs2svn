# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2009 CollabNet.  All rights reserved.
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

"""Classes for outputting the converted repository to bzr.

Relies heavily on the support for outputting to git, with a few tweaks to make
the dialect of the fast-import file more suited to bzr.

"""

from cvs2svn_lib.git_output_option import GitOutputOption


class BzrOutputOption(GitOutputOption):
  """An OutputOption that outputs to a git-fast-import formatted file, in a
  dialect more suited to bzr.
  """

  name = "Bzr"

  def __init__(
        self, dump_filename, revision_writer,
        max_merges=None, author_transforms=None,
        ):
    """Constructor.

    See superclass for meaning of parameters.
    """
    GitOutputOption.__init__(self, dump_filename, revision_writer, max_merges,
        author_transforms)

  def get_tag_fixup_branch_name(self, svn_commit):
    # Use a name containing '.', which is not allowed in CVS symbols, to avoid
    # conflicts (though of course a conflict could still result if the user
    # requests symbol transformations).
    return 'refs/heads/tag-fixup.%s' % svn_commit.symbol.name


