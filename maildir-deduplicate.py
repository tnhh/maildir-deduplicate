#!/usr/bin/python

##############################################################################
#
# Copyright (C) 2010 Kevin Deldycke <kevin@deldycke.com>
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

"""
  This script compare all mails in a maildir folder and subfolders,
  then delete duplicate mails.  You can give a list of mail headers
  to ignore when comparing mails between each others.  I used this
  script to clean up a messed maildir folder after I move several
  mails from a Lotus Notes database.

  Tested on MacOS X 10.6 with Python 2.6.2.
"""

import os
import re
import sys
import hashlib
from mailbox      import Maildir
from email.parser import Parser

# List of mail headers to ignore when computing the hash of a mail.
# BTW, don't worry: mail header manipulation methods are case-insensitive.
HEADERS_TO_IGNORE = [
  # Unique header generated by Lotus Notes on IMAP transfers
  'x-mimetrack',

  # This could differ e.g. if a mail was saved locally at the time it
  # was sent to a mailing list, a copy of the same mail could come
  # back from the list server with an extra footer attached
  'content-length',
]

# Since we're ignoring the Content-Length header for the reasons
# stated above, we limit the allowed difference between message sizes.
# If this is exceed, a RuntimeError is thrown, because this could
# point to message corruption somewhere.
SIZE_DIFFERENCE_THRESHOLD = 256 # bytes

def computeDigest(mail, ignored_headers):
  """ This method remove some mail headers before generating a digest of the message
  """
  # Make a local copy of the message to manipulate it. I haven't found
  # a cleaner way than passing through a intermediate string
  # representation.
  p = Parser()
  mail_copy = p.parsestr(mail.as_string(), headersonly = True)
  for header in mail_copy.keys():
    if header.lower() in HEADERS_TO_IGNORE \
    or header.lower().startswith("x-offlineimap-"):
      #show_progress("  ignoring header '%s'" % header)
      del mail_copy[header]

  #header_text, sep, payload = mail_copy.as_string().partition("\n\n")
  header_text = '\n'.join('%s: %s' % header for header in mail_copy.items())
  #print header_text

  return hashlib.sha224(header_text).hexdigest()

def collateFolderByHash(mails_by_hash, mail_folder):
  mail_count = 0
  show_progress("Processing %s mails in the %r folder..." % \
                  (len(mail_folder), mail_folder._path))
  for mail_id, message in mail_folder.iteritems():
    mail_hash = computeDigest(mail_folder.get(mail_id), HEADERS_TO_IGNORE)
    if mail_count > 0 and mail_count % 100 == 0:
      show_progress("  processed %d mails" % mail_count)
    #show_progress("  Hash is %s for mail %r" % (mail_hash, mail_id))
    if mail_hash not in mails_by_hash:
      mails_by_hash[mail_hash] = [ ]

    mail_file = os.path.join(mail_folder._path, mail_folder._lookup(mail_id))
    mails_by_hash[mail_hash].append((mail_file, message))
    mail_count += 1

  # We've analysed all mails in the current folder. Look in sub folders
  for folder_name in mail_folder.list_folders():
    print "Would look in", folder_name
    #processMails(mail_folder.get_folder(folder_name))

  return mail_count

def findDuplicates(mails_by_hash):
  duplicates = 0
  for digest, messages in mails_by_hash.iteritems():
    if len(messages) > 1:
      subject = messages[0][1].get('Subject')
      subject, count = re.subn('\s+', ' ', subject)
      print "\n" + subject
      duplicates += len(messages) - 1
      checkSizesComparable(messages)
      for mail_file, message in messages:
        print "  ", mail_file
    # else:
    #   print "unique:", messages[0]

  return duplicates

def sort_messages_by_size(messages):
  sizes = [ ]
  for mail_file, message in messages:
    size = os.path.getsize(mail_file)
    sizes.append((size, mail_file))
  def _sort_by_size(a, b):
    return cmp(a[0], b[0])
  sizes.sort(cmp = _sort_by_size)
  return sizes

def checkSizesComparable(messages):
  sizes = sort_messages_by_size(messages)
  smallest_size, smallest_file = sizes[0]

  for size, mail_file in sizes[1:]:
    if size > smallest_size + SIZE_DIFFERENCE_THRESHOLD:
      raise RuntimeError, \
        "%s was %d bytes long which is more than %d bytes longer than %s at %d. " % \
        (mail_file, size, SIZE_DIFFERENCE_THRESHOLD, smallest_file, smallest_size)
    # else:
    #   show_progress(
    #     "%s was %d bytes long which is less than %d bytes longer than %s at %d. " %
    #     (mail_file, size, SIZE_DIFFERENCE_THRESHOLD, smallest_file, smallest_size)
    #   )

def show_progress(msg):
  sys.stderr.write(msg + "\n")

def main():
  mails_by_hash = { }
  mail_count = 0

  for maildir_path in sys.argv[1:]:
    maildir = Maildir(maildir_path, factory = None)
    mail_count += collateFolderByHash(mails_by_hash, maildir)

  duplicates = findDuplicates(mails_by_hash)
  show_progress("\n%s duplicates in a total of %s mails." % \
                  (duplicates, mail_count))

main()
