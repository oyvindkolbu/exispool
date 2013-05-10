#!/local/bin/python
#coding: utf8
#
# Copyright 2009-2013 Ståle Kristoffersen <stalk@usit.uio.no>
#                     and Øyvind Kolbu <kolbu@usit.uio.no>.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#   2. Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# FREEBSD PROJECT OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# $Id: exispool.py,v 1.20 2013/05/10 10:01:51 kolbu Exp $

import fcntl
import os
import struct
import re
import string
import sys
import time

from optparse import OptionParser, OptionGroup, TitledHelpFormatter, \
                     IndentedHelpFormatter

version = "1.1"

class action(object):
    def __init__(self, options, tests):
	"""Save options and compile and regexes."""
	self.options = options
	self.matchcount = 0
	self.size = 0
        self.tests = tests

        # For each of the tests, precompile a regular expression.
        for test in tests:
            teststring = getattr(options,test)
            if teststring:
                teststring = teststring[0]
                self.matchcount += 1
                setattr(self, 're_'+test, re.compile(teststring,
                        re.DOTALL | re.IGNORECASE))

        if self.options.h_exim_user:
            self.matchcount += 1
            setattr(self,'re_h_exim_user',re.compile('\tuser \S*'+options.h_exim_user+
                                                     '\S* \(Exim \d',re.IGNORECASE))

        if self.options.h_by_host:
            self.matchcount += 1
            setattr(self,'re_h_by_host',re.compile('by [\w\.-]*'+options.h_by_host+
                                                     '[\w\.-]* with',re.IGNORECASE))
        if self.options.h_from_host:
            self.matchcount += 1
            setattr(self,'re_h_from_host',re.compile('from \S*'+options.h_from_host,
                                                     re.IGNORECASE))
        if self.options.is_frozen:
            self.matchcount +=1

        if self.options.is_not_frozen:
            self.matchcount += 1

    def handle(self, m):
        """Handle each message, m, according to the options given."""
	matches = 0
	ret = True

        for test in self.tests:
            if hasattr(self, 're_' + test) and hasattr(m,test):
                regex = getattr(self, 're_' + test)
                if regex.search(getattr(m,test)):
                    matches += 1

        if self.options.h_exim_user:
            regex = getattr(self,'re_h_exim_user')
            if regex.search(m.h_received):
                matches += 1

        if self.options.h_by_host:
            regex = getattr(self,'re_h_by_host')
            if regex.search(m.h_received):
                matches += 1

        if self.options.h_from_host:
            regex = getattr(self,'re_h_from_host')
            if regex.search(m.h_received):
                matches += 1

        if self.options.is_frozen:
            if hasattr(m,'frozen'):
                matches += 1

        if self.options.is_not_frozen:
            if not hasattr(m, 'frozen'):
                matches += 1
        
	if matches == self.matchcount:
	    if self.options.invert:
		ret = False
        # If matches found are not the matchcount we want, but options.invert
        # is set, revert the result.
	else:
	    if self.options.invert:
		ret = True
	    else:
		ret = False

	if ret:
	    # This message maches all the rules it's supposed to, do the correct
	    # action
	    if self.options.freeze:
		m.freeze()
	    elif self.options.thaw:
		m.thaw()

	    if self.options.size:
		self.size += m.size

	    if self.options.delete:
		m.delete()

            if self.options.list_eximid:
                print m.exim_id

            if self.options.list_header_path:
                print m.path

	return ret

class message(object):
        
    def __init__(self, path, exim_id, headers, verbose):
	"""save exim_id, stat the file for size and call _parseheader"""
	self.exim_id = exim_id
	self.path = path
        self.storeheaders = headers
        self._env_to = []
        self._delivered = []
        self.entire_header = ""
        self.size = 0
        try:
            self.size = os.path.getsize(self.path[:-2] + '-D')
        except OSError:
            return None
        if verbose:
            print path
        try:
            self._parseheader()
        except HeaderError, e:
            if verbose:
                print >>stderr, 'Failed parsing %s: %s' % (path, e)
            return None
            

    def _parseheader(self):
        """Parse the header, saving all important data to the message object"""

        def _get_entire_header(str,i):
            """
            Argument: str = value of the first header line
                      i   = index in lines

            If sample header lines are on the form:
            ---------------------------------------
            795T To: First Last <first@bar.com>,
             First2 Lastname <foo@bar.com>
            018  MIME-Version: 1.0
            ---------------------------------------
            Then str = "First Last <first@bar.com>,\n" and
            the function will return "First Last <first@bar.com>,
             First2 Lastname <foo@bar.com>"
            """

            ret = str

            while i+1 < lines_len:
                if lines[i+1][0] in (' ','\t'):
                    ret += lines[i+1]
                    i += 1
                else:
                    break

            return ret.rstrip(), i
           
        try:
            file = open(self.path)
        except IOError, e:
            raise HeaderError("Error reading %s" % self.path)
            
	i = 0 # line number
        lines = file.readlines()
        file.close()


        if not lines:
            raise HeaderError('Header file %s in empty' % self.path)
	
	# Sanity check: The first line in the file must contain the exim-id.
        line = lines[0].rstrip()
        if self.path.split('/')[-1] != line:
            raise HeaderError('File %s does not contain header %s' %
                                 (self.path, line))

        lines_len = len(lines)

        # Default start state for our state machine.
        state = 'STATIC'
        while i < lines_len:
            
            # Change state testing
            if state == 'STATIC' and lines[i][0] == '-':
                state = 'ACL'
            elif state == 'ACL' and lines[i][0] != '-':
                state = 'DELIVERED'
            elif state == 'DELIVERED' and lines[i][0:2] not in ('XX','YY','YN',
                                                               'NY','NN'):
                state = 'RECIPIENTCOUNT'
            elif state == 'RECIPIENTCOUNT':
                state = 'RECIPIENTS'
            elif state == 'RECIPIENTS' and not lines[i].rstrip():
                state = 'HEADER'
                i += 1 # Skip the blank line.

            # The first four lines of the file are always static.
	    # We are only interested in line 2 and 3:
            if state == 'STATIC':
                if i == 2:
                    self.env_from = lines[i].rstrip()
                elif i == 3:
                    self.age = int(time.time()) - int((lines[i]).split()[0])
	    # After the static lines, one or more acls are listed.
            # We are only interested in the -frozen acl, but in case of
            # acl-variables, "i" must be adjusted to start on a new acl.
            elif state == 'ACL':
                if lines[i].startswith('-frozen '):
                    self.frozen = True
                elif lines[i].startswith('-acl'):
                    # Format:
                    #-----------------
                    #  -aclm 18 24
                    #  blacklist 0 whitelist 0
                    #  
                    #  -aclc 2 13
                    #  127.0.0.1 783
                    #-----------------
                    #
                    # Where aclX numA numB is len(aclX_numA) = numB, where \n is only
                    # counted on the non-last line in a multiline acl.
                    name, num, size = lines[i].split()
                    size = int(size)
                    read = 0
                    val = ""
                    i += 1
                    while read < size:
                        if read > 0:
                            val += '\n'
                            read += 1
                        line = lines[i].rstrip('\n')
                        val += line
                        read += len(line)
                        if read < size:
                            i += 1
                    assert read == size

	    # Then a list of addresses that have been delivered.
            elif state == 'DELIVERED':
                if not lines[i][0:2] == 'XX':
                    rcpt = lines[i][3:-1]
                    self._delivered.append(rcpt)
	    # Then a number of deliveries
	    # (should be the number of adressesfound above)
            elif state == 'RECIPIENTCOUNT':
                self.rcpt_count = int(lines[i].rstrip())
	    # Then a complete list of recipients is listed
            elif state == 'RECIPIENTS':
                rcpt = lines[i].rstrip()
                self._env_to.append(rcpt)
	    # For the header-fields we save a few fields so it can be
	    # matched easier, but we still save the complete header
	    # so users can do regexp-maches on it.
            elif state == 'HEADER':
              
                # Skip the first entry on a new line, which indicates the size and
                # if a letter which means exim shows special interest.
                line = lines[i].split(' ',1)[1]

                # Remove extra whitespace from lines without a letter, e.g. "18  Subject:"
                # Only split on the first ':'
                attr, val = line.lstrip().split(':',1)
                # Remove the mandatory space after colon
                val = val[1:]
                attr = 'h_' + attr.lower()
                val, i = _get_entire_header(val,i)

                # Store some commonly used header, for convenience.
                if attr in self.storeheaders:
                    setattr(self, attr, val)
                elif attr == 'h_received':
                    if hasattr(self, 'h_received'):
                        self.h_received += '\n'+val
                    else:
                        self.h_received = val

                self.entire_header += '\n%s:%s' % (attr, val)
                self.size += len(val) + 1 # Include the rstrip()ed '\n'
            i += 1
        assert(self.rcpt_count == len(self._env_to))

        # Make a copy which is easier to regexp automatically from
        # getattr in the action class.
        self.env_to = ','.join(self._env_to)

    def __str__(self):
	"""Return a string representation of the message in exim format."""
        ret = '%s %05s %s %s' % (self._get_printable_age(),
                                 self._get_printable_size(), self.exim_id,
                                 self.env_from)
        if hasattr(self, 'frozen'):
            ret += ' *** frozen ***'

        for addr in self._env_to:
            if addr in self._delivered:
                ret += '\n\t D %s' % addr
            else:
                ret += '\n\t   %s' % addr
        return ret

    
    def _get_printable_age(self):
	"""Return in human readable age in the same way as exim."""
        MIN = 60.0
        HOUR = MIN * MIN
        DAY = 24 * HOUR
        # Display minutes if less than 100 minutes.
        if self.age < 100 * MIN:
            return '%2dm' % int(round(self.age / MIN))
        # And hours if less than 3 days
        elif self.age < 72 * HOUR:
            return '%2dh' % int(round(self.age / HOUR))
        else:
            return '%2dd' % int(round(self.age / DAY))

    # self.size is in bytes
    def _get_printable_size(self):
	"""Return the human readable size in the same way as exim."""
        KB = 1024
        MB = KB * KB

        if self.size < 10 * KB:
            return '%3.1fK' % (float(self.size) / KB)
        elif self.size < 1 * MB:
            return '%4dK' % (self.size / KB)
        elif self.size < 10 * MB:
            return '%3.1fM' % (float(self.size) / MB)
        else:
            return '%4dM' % (self.size / MB)

    def delete(self):
	"""Safely delete a message (-H, -D and -J)."""
	# Exim locks the data-file when it is sending it.
	# This means if we can get a lock, we can safely delete it
	file = self._lock()

	if file:
	    try:
		os.remove(self.path)
	    except OSError, e:
		print "Error while removing %s, skipping." % self.path
		file.close()
		return

	    try:
		os.remove(self.path[:-1] + "J")
	    except OSError, e:
		# the J file is not normally present, so just ignore this.
		pass

	    file.close()
	    datapath = self.path[:-1] + "D"
	    try:
		os.remove(datapath)
	    except OSError, e:
		print "Error while deleting %s, inconsistencies may exist" % datapath

    def freeze(self):
	"""Add -frozen to the header, indicating exim should not deliver it."""
	if hasattr(self, 'frozen'):
	    return

	lock = self._lock()
	if lock:
	    # Read in the old file:
	    file = open(self.path, "r+")
	    lines = file.readlines()
	    linein = 0
	    file.seek(0) # rewind
	    for line in lines:
		if(linein == 4):
		    file.write("-frozen " + str(int(time.time())) + "\n")
		    file.write(line)
		file.write(line)
		linein += 1
	    file.close()
	    lock.close()
	    self.frozen = True


    def thaw(self):
	"""Removes the -frozen line from the header, hence exim will attempt to deliver it"""
	if not hasattr(self, 'frozen'):
	    return

	lock = self._lock()
	if lock:
	    file = open(self.path, "r+")
	    lines = file.readlines()
	    file.close()
	    file = open(self.path, "w")
	    for line in lines:
		if line[:8] == "-frozen ":
		    continue
		else:
		    file.write(line)
	    file.close()
	    lock.close()
	    delattr(self, 'frozen')

    def _lock(self):
	"""Get a lock on the -D-file.

	This is needed in order to not touch the same files as exim at the same
	time as exim."""
	datapath = self.path[:-1] + "D"
	file = open(datapath, 'a')
	try:
	    fcntl.lockf(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
	except IOError, e:
	    print "Unable to aquire a lock on %s, skipping" % self.exim_id
	    return
	return file

    def get_delivered_domains(self):
        """List all domains which have at least been delivered once."""
        for addr in self._delivered:
            yield addr.split('@')[1]

    def get_undelivered_domains(self):
        """List all domains which have not yet been delivered."""
        for addr in set.difference(set(self._env_to), set(self._delivered)):
            yield addr.split('@')[1]


class HeaderError(Exception):
    pass

class options(object):

    def usage(self,msg=None):
        sys.stderr.write('usage: %s [options] spool1 [spool2...]\n' % sys.argv[0])
        if msg:
            sys.stderr.write(msg + "\n")
        sys.exit(1)

    def __init__(self, arguments=sys.argv[1:]):
	"""Use optionParser to parse the argument-list.
	
	We also save each option that a message should match
	in the 'matching'-array. This is so the action-class
	can figure out if the message has matched all required
	options.
	"""
	# Parse arguments
        usage_str = "usage: %prog [options] spool1 [spool2 ...]"

	parser = OptionParser(usage_str,
			      formatter=IndentedHelpFormatter(
                                        max_help_position=30,
					indent_increment=0))

	# arguments:
	parser.add_option("-v", "--verbose",
			action="store_true", dest="verbose",
			help="be verbose")
        parser.add_option("-V", "--version",
                        action="store_true", dest="version",
                        help="show version")
	parser.add_option("-o", "--optionfile", metavar="FILE",
			dest="cfgfile",
			help="spesify a configuration file at FILE")
	
       
        # Matching rules
        self.matching = []
        rules = OptionGroup(parser, "These options control which messages "
                                    "will be matched. ADDR/STRING is a regular expression")
        rules.add_option("-f", "--from", metavar="ADDR",
                        dest="env_from", action="append",
                        help="envelope from matches ADDR")
        self.matching.append('env_from')
        rules.add_option("-F", "--hfrom", metavar="ADDR",
                        dest="h_from", action="append",
                        help="header \"From\" matches ADDR")
        self.matching.append('h_from')
        rules.add_option("-E", "--hsubject", metavar="STRING",
                        dest="h_subject", action="append",
                        help="header \"Subject\" matches STRING")
        self.matching.append('h_subject')
        rules.add_option("-t", "--to", metavar="ADDR",
                        dest="env_to", action="append",
                        help="envelope to matches ADDR")
        self.matching.append('env_to')
        rules.add_option("-T", "--hto", metavar="ADDR",
                        dest="h_to", action="append",
                        help="header \"To\" matches ADDR")
        self.matching.append('h_to')
        rules.add_option("-C", "--cc", metavar="ADDR",
                        dest="h_cc", action="append",
                        help="header \"Cc\" matches ADDR")
        self.matching.append('h_cc')
        rules.add_option("-M", "--message-id", metavar="ADDR",
                        dest="h_message-id", action="append",
                        help="header \"Message-Id\" matches ADDR")
        self.matching.append('h_message-id')
        rules.add_option("-R", "--reply-to", metavar="ADDR",
                        dest="h_reply-to", action="append",
                        help="header \"Reply-To\" matches ADDR")
        self.matching.append('h_reply-to')
        rules.add_option("-S", "--smtp-user", metavar="ADDR",
                        dest="h_exim_user",
                        help="exim smtp user matches ADDR")
        rules.add_option("-m", "--from-host", metavar="HOST",
                        dest="h_from_host",
                        help="message came from HOST")
        rules.add_option("-b", "--by-host", metavar="HOST",
                        dest="h_by_host",
                        help="message passed by HOST")
        rules.add_option("-i", "--invert", action="store_true",
                        dest="invert", help="invert matches")
        rules.add_option("-z", "--frozen", action="store_true",
                        dest="is_frozen", help="match if message is frozen")
        rules.add_option("-n", "--not-frozen", action="store_true",
                        dest="is_not_frozen", help="match if message is not frozen")
        parser.add_option_group(rules)

	# actions
	act = OptionGroup(parser, "These options control what to do with "
				  "messages that match")
	act.add_option("-l", "--list",
			action="store_true", dest="list",
			help="list matching messages")
        act.add_option("-L", "--list-exim-id",
                        action="store_true", dest="list_eximid",
                        help="only list exim queue id")
        act.add_option("-p", "--list-header-path",
                        action="store_true", dest="list_header_path",
                        help="list path to header file")
        act.add_option("-q", "--quiet",
                        action="store_false", dest="list",
                        help="disable default output")
	act.add_option("-d", "--delete",
			action="store_true", dest="delete",
			help="delete matching messages")
	act.add_option("-c", "--count",
			action="store_true", dest="count",
			help="print number of matches")
	act.add_option("-s", "--size",
			action="store_true", dest="size",
			help="print total size of messages matching")
	act.add_option("-r", "--freeze",
			action="store_true", dest="freeze",
			help="freeze the messages")
	act.add_option("-H", "--thaw",
			action="store_true", dest="thaw",
			help="thaw (unfreeze) the messages")
	act.add_option("-D", "--delivered-domains",
			action="store_true", dest="list_delivered",
			help="list delivered domains")
	act.add_option("-u", "--undelivered-domains",
			action="store_true", dest="list_undelivered",
			help="list undelivered domains")
	parser.add_option_group(act)

	# defaults
	parser.set_defaults(cfgfile="/etc/exispoolcfg")
        parser.set_defaults(list=True)

	(self.opt, self.args) = parser.parse_args(arguments)

        if self.opt.list_eximid or self.opt.list_header_path:
            self.opt.list = False

        for o in self.matching:
            t = getattr(self.opt,o)
            if t and len(t) > 1:
                #print t
                raise OptionsError("Same adder field, '%s' specified more than once. Use regex." % o)
	
	# only read the configfile if no spools are spesified on the
	# command line.
        if len(self.args) == 0:
            if os.path.isfile(self.opt.cfgfile):
                try:
                    file = open(self.opt.cfgfile, 'r')
                    self.spools = map(string.strip, file.readlines())
                    file.close()
                except:
                    raise OptionsError("Could not read %s" % self.opt.cfgfile)
            elif not self.opt.version:
                raise OptionsError('No spools defined')
        else:
	    self.spools = self.args

class OptionsError(Exception):

    def __init__(self, msg):
        self.msg = msg


class spools(object):
    """Spools. Will store all matching messages found in given spool(s)."""

    m = []
    
    def __init__(self, option, action):
	"""Save action and run self.populate on all paths given.
	
	action is an instance of the action-class and defines
	tests on a message and certain actions, like delete
	and freeze.
	"""
	self.msgcount = 0
	self.size = 0
	self.matches = 0
	self.nonmatches = 0
	self.action = action
        self.opt = option.opt
        for path in option.spools:
            if self.opt.verbose:
                print 'Adding spool: ' + path
            self.populate(path)

    def populate(self, path):
	"""Iterate over all subdirs of the path and add all messages.
	
	First it checks if the path has a subdir called 'input'. Since all
	exim spools should have that sub directory we rais a SpoolError if
	it is not there. We then walk the input directory and for every file
	that ends on -H create a new message, tells the action-object to
	handle it, and appends it to the global array 'm' if handle returns
	true.
	"""
	if os.path.isdir(os.path.join(path, 'input')):
	    for root, dirs, files in os.walk(os.path.join(path, 'input')):
		for file in files:
		    if file[-2:] == "-H":
			self.msgcount += 1;
			filepath = os.path.join(root, file)
                        me = message(filepath,file[:-2],self.action.tests,self.opt.verbose)
                        if me is not None:
                            self.size += me.size
                            if (self.action.handle(me)):
                                self.m.append(me)
	else:
	    raise SpoolError("Error, '%s' is not an exim spool!" % path)

   
    def list(self, sortby=['age','size']):
	"""Sort messages, default by age then size, and the list them."""

        def my_sort(a, b):
            c = 0
            for attr in sortby:
                c = cmp(getattr(b,attr), getattr(a,attr))
                if c != 0:
                    return c
            return c

        self.m.sort(my_sort)

        for mail in self.m:
            print str(mail) + '\n'

    def _list_domains(self, func):
	"""return a list of every domain with a count of (un)delivered mail"""
        dom = {}
        dom.setdefault(0)

        for mail in self.m:
            for domain in getattr(mail,func)():
                dom[domain] = dom.get(domain,0) + 1

        del dom[0] # Remove default value.
        result = [ (count, domain) for domain, count in dom.items() ]
        result.sort()
        
        return result

    def list_delivered(self):
	"""List the number of delivered mails for each domain."""
        domains = self._list_domains('get_delivered_domains')
        print 'Delivered domains:'
        print '\n'.join('%7d %s' % (count, domain) for count,domain in domains)

    def list_undelivered(self):
	"""List the number of undelivered mails for each domain."""
        domains = self._list_domains('get_undelivered_domains')
        print 'Undelivered domains:'
        print '\n'.join('%7d %s' % (count, domain) for count,domain in domains)

    def count(self):
	"""Return the number of messages matched."""
	return len(self.m)

class SpoolError(Exception):
    def __init__(self, msg):
        self.msg = msg

def main():
    """ exispool: Manages spools for exim"""

    # Initialize the options handler.
    try: 
        option = options()
    except OptionsError, e:
        sys.stderr.write(e.msg + "\n")
        return 1

    opt = option.opt

    # Initialze the action handler.
    a = action(opt, option.matching)

    if opt.version:
        print "%s: %s" % (sys.argv[0].split('/')[-1],version)
        return 0

    # read and perform the matching options on the messages found in
    # option.spools
    try:
        sp = spools(option,a)
    except SpoolError, e:
        sys.stderr.write(e.msg + "\n")
        return 1

    # Print the result in default "exim -bp" format.
    if opt.list:
        if opt.verbose:
            print "Listing matched messages:"
        sp.list()

    # Print the number of matches, "exim -bp"
    if opt.count:
	print "Matching messages: %s" % sp.count()

    # Print total size of spool(s), no exim equivalent.
    if opt.size:
	print "Size: %s" % a.size

    # Print all domains to whom exim have delivered at least one address.
    if opt.list_delivered:
        sp.list_delivered()

    # Print all domains to whom exim have failed to delivered at least one
    # address.
    if opt.list_undelivered:
        sp.list_undelivered()

    return 0

if __name__ == "__main__":
    sys.exit(main())

