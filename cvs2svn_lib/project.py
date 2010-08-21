# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2000-2008 CollabNet.  All rights reserved.
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

"""This module contains database facilities used by cvs2svn."""


import os
import cPickle

from cvs2svn_lib.context import Ctx
from cvs2svn_lib import db
from cvs2svn_lib.common import FatalError
from cvs2svn_lib.common import IllegalSVNPathError
from cvs2svn_lib.common import normalize_svn_path
from cvs2svn_lib.common import verify_paths_disjoint
from cvs2svn_lib.symbol_transform import CompoundSymbolTransform
from sqlalchemy.orm.exc import NoResultFound


class FileInAndOutOfAtticException(Exception):
  def __init__(self, non_attic_path, attic_path):
    Exception.__init__(
        self,
        "A CVS repository cannot contain both %s and %s"
        % (non_attic_path, attic_path))

    self.non_attic_path = non_attic_path
    self.attic_path = attic_path


def normalize_ttb_path(opt, path, allow_empty=False):
  try:
    return normalize_svn_path(path, allow_empty)
  except IllegalSVNPathError, e:
    raise FatalError('Problem with %s: %s' % (opt, e,))


class CVSProject(db.Base):
  """A project within a CVS repository."""

  __tablename__ = 'projects'

  id = db.Column(db.Integer, primary_key=True)
  project_cvs_repos_path = db.Column(db.Text)
  cvs_repos_root = db.Column(db.Text)
  cvs_module = db.Column(db.Text)

  def __init__(
        self, project_cvs_repos_path, cvs_repos_root, cvs_module
        ):
    """Create a new CVSProject record.

    ID is a unique id for this project.  PROJECT_CVS_REPOS_PATH is the
    main CVS directory for this project (within the filesystem).

    INITIAL_DIRECTORIES is an iterable of all SVN directories that
    should be created when the project is first created.  Normally,
    this should include the trunk, branches, and tags directory.

    SYMBOL_TRANSFORMS is an iterable of SymbolTransform instances
    which will be used to transform any symbol names within this
    project."""

    self.project_cvs_repos_path = project_cvs_repos_path
    self.cvs_repos_root = cvs_repos_root
    self.cvs_module = cvs_module

    self._initial_directories = []
    self.symbol_transform = CompoundSymbolTransform([])

    # The ID of the Trunk instance for this CVSProject.  This member is
    # filled in during CollectRevsPass.
    self.trunk_id = None

    # The ID of the CVSDirectory representing the root directory of
    # this project.  This member is filled in during CollectRevsPass.
    self.root_cvs_directory_id = None

  def set_initial_directories(self, initial_directories):
    # The SVN directories to add when the project is first created:
    self._initial_directories = []

    for path in initial_directories:
      try:
        path = normalize_svn_path(path, False)
      except IllegalSVNPathError, e:
        raise FatalError(
            'Initial directory %r is not a legal SVN path: %s'
            % (path, e,)
            )
      self._initial_directories.append(path)

    verify_paths_disjoint(*self._initial_directories)

  def set_symbol_transform(self, symbol_transforms):
    # A list of transformation rules (regexp, replacement) applied to
    # symbol names in this project.
    if symbol_transforms is None:
      symbol_transforms = []

    self.symbol_transform = CompoundSymbolTransform(symbol_transforms)

  def __eq__(self, other):
    return self.id == other.id

  def __cmp__(self, other):
    return cmp(self.cvs_module, other.cvs_module) \
           or cmp(self.id, other.id)

  def __hash__(self):
    return self.id

  @staticmethod
  def determine_repository_root(path):
    """Ascend above the specified PATH if necessary to find the
    cvs_repository_root (a directory containing a CVSROOT directory)
    and the cvs_module (the path of the conversion root within the cvs
    repository).  Return the root path and the module path of this
    project relative to the root.

    NB: cvs_module must be seperated by '/', *not* by os.sep."""

    def is_cvs_repository_root(path):
      return os.path.isdir(os.path.join(path, 'CVSROOT'))

    original_path = path
    cvs_module = ''
    while not is_cvs_repository_root(path):
      # Step up one directory:
      prev_path = path
      path, module_component = os.path.split(path)
      if path == prev_path:
        # Hit the root (of the drive, on Windows) without finding a
        # CVSROOT dir.
        raise FatalError(
            "the path '%s' is not a CVS repository, nor a path "
            "within a CVS repository.  A CVS repository contains "
            "a CVSROOT directory within its root directory."
            % (original_path,))

      cvs_module = module_component + "/" + cvs_module

    return path, cvs_module

  def transform_symbol(self, cvs_file, symbol_name, revision):
    """Transform the symbol SYMBOL_NAME.

    SYMBOL_NAME refers to revision number REVISION in CVS_FILE.
    REVISION is the CVS revision number as a string, with zeros
    removed (e.g., '1.7' or '1.7.2').  Use the renaming rules
    specified with --symbol-transform to possibly rename the symbol.
    Return the transformed symbol name, the original name if it should
    not be transformed, or None if the symbol should be omitted from
    the conversion."""

    return self.symbol_transform.transform(cvs_file, symbol_name, revision)

  def get_trunk(self):
    """Return the Trunk instance for this project.

    This method can only be called after self.trunk_id has been
    initialized in CollectRevsPass."""

    return Ctx()._symbol_db.get_symbol(self.trunk_id)

  def get_root_cvs_directory(self):
    """Return the root CVSDirectory instance for this project.

    This method can only be called after self.root_cvs_directory_id
    has been initialized in CollectRevsPass."""

    return Ctx()._cvs_path_db.get_path(self.root_cvs_directory_id)

  def get_initial_directories(self):
    """Generate the project's initial SVN directories.

    Yield as strings the SVN paths of directories that should be
    created when the project is first created."""

    # Yield the path of the Trunk symbol for this project (which might
    # differ from the one passed to the --trunk option because of
    # SymbolStrategyRules).  The trunk path might be '' during a
    # trunk-only conversion, but that is OK because DumpstreamDelegate
    # considers that directory to exist already and will therefore
    # ignore it:
    yield self.get_trunk().base_path

    for path in self._initial_directories:
      yield path

  def __str__(self):
    return self.project_cvs_repos_path


def create_project(
                    project_cvs_repos_path,
                    initial_directories=[],
                    symbol_transforms=None,
                    ):
    project_cvs_repos_path = os.path.normpath(project_cvs_repos_path)
    if not os.path.isdir(project_cvs_repos_path):
      raise FatalError("The specified CVS repository path '%s' is not an "
                       "existing directory." % project_cvs_repos_path)

    cvs_repos_root, cvs_module = \
        CVSProject.determine_repository_root(
            os.path.abspath(project_cvs_repos_path))

    ctx = Ctx()
    sess = ctx.session
    CVSProject.metadata.create_all(ctx.engine)
    try:
        project = sess.query(CVSProject).filter_by(project_cvs_repos_path=project_cvs_repos_path).one()
    except NoResultFound:
        project = CVSProject(project_cvs_repos_path, cvs_repos_root, cvs_module)
        sess.add(project)
        sess.commit()
    project.set_symbol_transform(symbol_transforms)
    project.set_initial_directories(initial_directories)
    return project


def read_projects(filename):
  retval = {}
  for project in cPickle.load(open(filename, 'rb')):
    retval[project.id] = project
  return retval


def write_projects(filename):
  cPickle.dump(Ctx()._projects.values(), open(filename, 'wb'), -1)


