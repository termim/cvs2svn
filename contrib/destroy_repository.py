#! /usr/bin/python

# (Be in -*- python -*- mode.)
#
# ====================================================================
# Copyright (c) 2006 CollabNet.  All rights reserved.
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

"""Usage: destroy_repository.py OPTION... PATH...

Strip the text content out of RCS-format files.

*** This script irretrievably destroys any RCS files that it is applied to!

This script attempts to strip the file text, log messages, and author
names out of RCS files.  (This is useful to make test cases smaller
and to remove much of the proprietary information that is stored in a
repository.)  Note that this script does NOT obliterate other
information that might also be considered proprietary: file names,
commit dates, etc.  In fact, it's not guaranteed even to obliterate
all of the file text, or to do anything else for that matter.

The following OPTIONs are recognized:
  --all       destroy all data (this is the default if no options are given)
  --data      destroy revision data (file contents) only
  --metadata  destroy revision metadata (author, log message, description) only
  --no-X      where X is one of the above options negates the meaning of that
              option.

Each PATH that is a *,v file will be stripped.

Each PATH that is a directory will be traversed and all of its *,v
files stripped.

Other PATHs will be ignored.


Examples of usage:
  destroy_repository.py PATH
        destroys all data in PATH

  destroy_repository.py --all PATH
        same as above

  destroy_repository.py --data PATH
        destroys only revision data

  destroy_repository.py --no-data PATH
        destroys everything but revision data

  destroy_repository.py --data --metadata PATH
        destroys revision data and metadata only

---->8----

The *,v files must be writable by the user running the script.
Typically CVS repositories are read-only, so you might have to run
something like

    $ chmod -R ug+w my/repo/path

before running this script.

Most cvs2svn behavior is completely independent of the text contained
in an RCS file.  (The text is not even looked at until OutputPass.)

The idea is to use this script when preparing test cases for problems
that you experience with cvs2svn.  Instead of sending us your whole
CVS repository, you should:

1. Make a copy of the original repository

2. Run this script on the copy (NEVER ON THE ORIGINAL!!!)

3. Verify that the problem still exists when you use cvs2svn to
   convert the 'destroyed' copy

4. Send us the 'destroyed' copy along with the exact cvs2svn version
   that you used, the exact command line that you used to start the
   conversion, and the options file if you used one.

Please also consider using shrink_test_case.py to localize the problem
even further.

"""

import sys
import os
import shutil
import re
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(sys.argv[0])))

from cvs2svn_lib.key_generator import KeyGenerator
import cvs2svn_rcsparse
from rcs_file_filter import WriteRCSFileSink
from rcs_file_filter import FilterSink


# Which components to be destroyed. Default to all.
destroy = {
    'data': True,
    'metadata': True,
    }

tmpdir = 'destroy_repository-tmp'

file_key_generator = KeyGenerator(1)

def get_tmp_filename():
    return os.path.join(tmpdir, 'f%07d.tmp' % file_key_generator.gen_id())


class Substituter:
    def __init__(self, template):
        self.template = template
        self.key_generator = KeyGenerator(1)

        # A map from old values to new ones.
        self.substitutions = {}

    def get_substitution(self, s):
        r = self.substitutions.get(s)
        if r == None:
            r = self.template % self.key_generator.gen_id()
            self.substitutions[s] = r
        return r


class LogSubstituter(Substituter):
    # If a log messages matches any of these regular expressions, it
    # is passed through untouched.
    untouchable_log_res = [
        re.compile(r'^Initial revision\n$'),
        re.compile(r'^file .+ was initially added on branch .+\.\n$'),
        re.compile(r'^\*\*\* empty log message \*\*\*\n$'),
        re.compile(r'^initial checkin$'),
        ]

    def __init__(self):
        Substituter.__init__(self, 'log %d')

    def _is_untouchable(self, log):
        for untouchable_log_re in self.untouchable_log_res:
            if untouchable_log_re.search(log):
                return True
        return False

    def get_substitution(self, log):
        if self._is_untouchable(log):
            return log
        else:
            return Substituter.get_substitution(self, log)


class DestroyerFilterSink(FilterSink):
    def __init__(self, author_substituter, log_substituter, sink):
        FilterSink.__init__(self, sink)

        self.author_substituter = author_substituter
        self.log_substituter = log_substituter

    def define_revision(
        self, revision, timestamp, author, state, branches, next
        ):
        if destroy['metadata']:
            author = self.author_substituter.get_substitution(author)
        FilterSink.define_revision(
            self, revision, timestamp, author, state, branches, next
            )

    def set_description(self, description):
        if destroy['metadata']:
            description = ''
        FilterSink.set_description(self, description)

    def set_revision_info(self, revision, log, text):
        if destroy['data']:
            text = ''
        if destroy['metadata']:
            log = self.log_substituter.get_substitution(log)
        FilterSink.set_revision_info(self, revision, log, text)


class FileDestroyer:
    def __init__(self):
        self.log_substituter = LogSubstituter()
        self.author_substituter = Substituter('author%d')

    def destroy_file(self, filename):
        tmp_filename = get_tmp_filename()
        f = open(tmp_filename, 'wb')
        cvs2svn_rcsparse.parse(
            open(filename, 'rb'),
            DestroyerFilterSink(
                self.author_substituter,
                self.log_substituter,
                WriteRCSFileSink(f),
                )
            )
        f.close()

        # Replace the original file with the new one:
        os.remove(filename)
        shutil.move(tmp_filename, filename)

    def visit(self, dirname, names):
        for name in names:
            path = os.path.join(dirname, name)
            if os.path.isfile(path) and path.endswith(',v'):
                sys.stderr.write('Destroying %s...' % path)
                self.destroy_file(path)
                sys.stderr.write('done.\n')
            elif os.path.isdir(path):
                # Subdirectories are traversed automatically
                pass
            else:
                sys.stderr.write('File %s is being ignored.\n' % path)

    def destroy_dir(self, path):
        os.path.walk(path, FileDestroyer.visit, self)


def usage_abort(msg):
    if msg:
        print >>sys.stderr, "ERROR:", msg
        print >>sys.stderr
    # Use this file's docstring as a usage string, but only the first part
    print __doc__.split('\n---->8----', 1)[0]
    sys.exit(1)

if __name__ == '__main__':
    if not os.path.isdir(tmpdir):
        os.makedirs(tmpdir)

    # Paths to be destroyed
    paths = []

    # Command-line argument processing
    first_option = True
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            # Option processing
            option = arg[2:].lower()
            value = True
            if option.startswith("no-"):
                value = False
                option = option[3:]
            if first_option:
                # Use the first option on the command-line to determine the
                # default actions. If the first option is negated (i.e. --no-X)
                # the default action should be to destroy everything.
                # Otherwise, the default action should be to destroy nothing.
                # This makes both positive and negative options work
                # intuitively (e.g. "--data" will destroy only data, while
                # "--no-data" will destroy everything BUT data).
                for d in destroy.keys():
                    destroy[d] = not value
                first_option = False
            if option in destroy:
                destroy[option] = value
            elif option == "all":
                for d in destroy.keys():
                    destroy[d] = value
            else:
                usage_abort("Unknown OPTION '%s'" % arg)
        else:
            # Path argument
            paths.append(arg)

    if not paths:
        usage_abort("No PATH given")

    # Destroy given PATHs
    file_destroyer = FileDestroyer()
    for path in paths:
        if os.path.isfile(path) and path.endswith(',v'):
            file_destroyer.destroy_file(path)
        elif os.path.isdir(path):
            file_destroyer.destroy_dir(path)
        else:
            sys.stderr.write('PATH %s is being ignored.\n' % path)


