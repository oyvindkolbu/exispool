#!/local/bin/python
#coding: latin-1
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
# Test suite for exispool.
# 
# $Id: tests.py,v 1.4 2013/05/10 09:50:23 kolbu Exp $

import os
import shutil
import sys
import unittest

class TestExispool(unittest.TestCase):
  
    testspool = '/tmp/exispool-test'
    configfile = 'testspool/configfile'
    # Will be ran before each test, and will create new testspools.
    def setUp(self):
        # Used to create testspool /tmp/exispool-test/, to make
        # sure that each test will have a pristine environment
        shutil.copytree('testspool',self.testspool)

    # And likewise clean up after each test.
    def tearDown(self):
        shutil.rmtree(self.testspool)

    def test_options_no_spools(self):
        """ Test without any arguments to options() """
        from exispool import options,OptionsError
        sys.argv = ['exispool']
        self.assertRaises(OptionsError, options)

    def test_options_not_valid_spool(self):
        """ Test options with at not valid spool path"""
        from exispool import options,spools,SpoolError
        self.assertRaises(SpoolError, spools,options(['/nonexistant']),None)

    def test_options_valid_spool_no_arguments(self):
        """ Test that the default arguments get set properly """
        from exispool import options
        options = options([self.testspool])
        self.assertEqual(options.spools,[self.testspool])
        opt = options.opt
        # program options
        self.assertEqual(opt.verbose,None)
        self.assertEqual(opt.cfgfile,'/etc/exispoolcfg')
        # matching options
        self.assertEqual(opt.env_from,None)
        self.assertEqual(opt.h_from,None)
        self.assertEqual(opt.env_to,None)
        self.assertEqual(opt.h_to,None)
        self.assertEqual(opt.h_cc,None)
        self.assertEqual(opt.h_exim_user,None)
        self.assertEqual(opt.h_from_host,None)
        self.assertEqual(opt.h_by_host,None)
        self.assertEqual(opt.invert,None)
        self.assertEqual(opt.is_frozen,None)
        self.assertEqual(opt.is_not_frozen,None)
        # actions
        self.assertEqual(opt.list,True)
        self.assertEqual(opt.list_eximid,None)
        self.assertEqual(opt.list_header_path,None)
        self.assertEqual(opt.delete,None)
        self.assertEqual(opt.count,None)
        self.assertEqual(opt.size,None)
        self.assertEqual(opt.freeze,None)
        self.assertEqual(opt.thaw,None)
        self.assertEqual(opt.list_delivered,None)
        self.assertEqual(opt.list_undelivered,None)

    def test_options_valid_spool_short_arguments(self):
        """ Test that short arguments get set properly """
        from exispool import options
        # TODO: Expand to all options.
        args = [self.testspool,
                '-v',
                '-o', self.configfile,
                '-f', 'test_envfrom',
                '-F', 'test_headerfrom',
                '-t', 'test_envto']
        opt = options(args).opt
        # program options
        self.assertEqual(opt.verbose,True)
        self.assertEqual(opt.cfgfile,self.configfile)
        # matching options
        self.assertEqual(opt.env_from,['test_envfrom'])
        self.assertEqual(opt.h_from,  ['test_headerfrom'])
        self.assertEqual(opt.env_to, ['test_envto'])
        self.assertEqual(opt.h_to,None)
        self.assertEqual(opt.h_cc,None)
        self.assertEqual(opt.h_exim_user,None)
        self.assertEqual(opt.h_from_host,None)
        self.assertEqual(opt.h_by_host,None)
        self.assertEqual(opt.invert,None)
        self.assertEqual(opt.is_frozen,None)
        self.assertEqual(opt.is_not_frozen,None)
        # actions
        self.assertEqual(opt.list,True)
        self.assertEqual(opt.list_eximid,None)
        self.assertEqual(opt.list_header_path,None)
        self.assertEqual(opt.delete,None)
        self.assertEqual(opt.count,None)
        self.assertEqual(opt.size,None)
        self.assertEqual(opt.freeze,None)
        self.assertEqual(opt.thaw,None)
        self.assertEqual(opt.list_delivered,None)
        self.assertEqual(opt.list_undelivered,None)

    def test_options_valid_spool_long_arguments(self):
        """ Test that long arguments get set properly """
        from exispool import options
        # TODO: Expand to all options.
        args = [self.testspool,
                '--verbose',
                '--cc', 'test_headercc',
                '--frozen',
                '--list-exim-id',
                '--delete']
        opt = options(args).opt
        # program options
        self.assertEqual(opt.verbose,True)
        self.assertEqual(opt.cfgfile,'/etc/exispoolcfg')
        # matching options
        self.assertEqual(opt.env_from,None)
        self.assertEqual(opt.h_from,None)
        self.assertEqual(opt.env_to,None)
        self.assertEqual(opt.h_to,None)
        self.assertEqual(opt.h_cc,['test_headercc'])
        self.assertEqual(opt.h_exim_user,None)
        self.assertEqual(opt.h_from_host,None)
        self.assertEqual(opt.h_by_host,None)
        self.assertEqual(opt.invert,None)
        self.assertEqual(opt.is_frozen,True)
        self.assertEqual(opt.is_not_frozen,None)
        # actions
        self.assertEqual(opt.list,False)
        self.assertEqual(opt.list_eximid,True)
        self.assertEqual(opt.list_header_path,None)
        self.assertEqual(opt.delete,True)
        self.assertEqual(opt.count,None)
        self.assertEqual(opt.size,None)
        self.assertEqual(opt.freeze,None)
        self.assertEqual(opt.thaw,None)
        self.assertEqual(opt.list_delivered,None)
        self.assertEqual(opt.list_undelivered,None)

    def test_spools(self):
        """ Test that the spools class is working properly """
        from exispool import action,options,spools
        # TODO: Expand to all options.
        args = [self.testspool,
                '--cc', 'example.no',
                '--not-frozen']
        o = options(args)
        a = action(o.opt, o.matching)
        s = spools(o,a)
        self.assertEqual(o.opt.h_cc,['example.no'])
        self.assertEqual(o.opt.is_not_frozen,True)
        self.assertEqual(s.count(),1)
        
if __name__  == '__main__':
    unittest.main()
