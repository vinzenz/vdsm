#
# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA
#
# Refer to the README and COPYING files for full details of the license
#

from xml.dom import minidom

from testrunner import VdsmTestCase as TestCaseBase
from monkeypatch import MonkeyPatch

import caps
import numaUtils

import vmTests


_VM_RUN_FILE_CONTENT = """
    <domstatus state='running' reason='booted' pid='12262'>
      <monitor path='/var/lib/libvirt/qemu/testvm.monitor'
               json='1' type='unix'/>
        <vcpus>
          <vcpu pid='12266'/>
          <vcpu pid='12267'/>
          <vcpu pid='12268'/>
          <vcpu pid='12269'/>
        </vcpus>
    </domstatus>"""


class FakeSuperVdsm:
    def __init__(self):
        pass

    def getProxy(self):
        return self

    def getVcpuNumaMemoryMapping(self, vmName):
        return {0: [0, 1], 1: [0, 1], 2: [0, 1], 3: [0, 1]}


class FakeAdvancedStatsFunction:
    def __init__(self):
        pass

    def getStats(self):
        return [], [(0, 1, 19590000000L, 1),
                    (1, 1, 10710000000L, 1),
                    (2, 1, 19590000000L, 0),
                    (3, 1, 19590000000L, 2)], 15


class FakeVmStatsThread:
    def __init__(self, vm):
        self._vm = vm
        self.sampleVcpuPinning = FakeAdvancedStatsFunction()


class TestNumaUtils(TestCaseBase):

    @MonkeyPatch(minidom, 'parse',
                 lambda x: minidom.parseString(_VM_RUN_FILE_CONTENT))
    def testVcpuPid(self):
        vcpuPids = numaUtils.getVcpuPid('testvm')
        expectedVcpuPids = {0: '12266',
                            1: '12267',
                            2: '12268',
                            3: '12269'}
        self.assertEqual(vcpuPids, expectedVcpuPids)

    @MonkeyPatch(numaUtils, 'supervdsm', FakeSuperVdsm())
    @MonkeyPatch(caps,
                 'getNumaTopology',
                 lambda: {'0': {'cpus': [0, 1, 2, 3],
                                'totalMemory': '49141'},
                          '1': {'cpus': [4, 5, 6, 7],
                                'totalMemory': '49141'}})
    def testVmNumaNodeRuntimeInfo(self):
        VM_PARAMS = {'guestNumaNodes': [{'cpus': '0,1',
                                         'memory': '1024',
                                         'nodeIndex': 0},
                                        {'cpus': '2,3',
                                         'memory': '1024',
                                         'nodeIndex': 1}]}
        with vmTests.FakeVM(VM_PARAMS) as fake:
            fake._vmStats = FakeVmStatsThread(fake)
            expectedResult = {'0': [0, 1], '1': [0, 1]}
            vmNumaNodeRuntimeMap = numaUtils.getVmNumaNodeRuntimeInfo(fake)
            self.assertEqual(expectedResult, vmNumaNodeRuntimeMap)
