"""
This file is part of Arakoon, a distributed key-value store. Copyright
(C) 2010 Incubaid BVBA

Licensees holding a valid Incubaid license may use this file in
accordance with Incubaid's Arakoon commercial license agreement. For
more information on how to enter into this agreement, please contact
Incubaid (contact details can be found on www.arakoon.org/licensing).

Alternatively, this file may be redistributed and/or modified under
the terms of the GNU Affero General Public License version 3, as
published by the Free Software Foundation. Under this license, this
file is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.

See the GNU Affero General Public License for more details.
You should have received a copy of the
GNU Affero General Public License along with this program (file "COPYING").
If not, see <http://www.gnu.org/licenses/>.
"""
import socket
import logging

import RemoteControlProtocol as RCP

def collapse(ip, port, clusterId, n):
    """
    tell the node listening on (ip, port) to collapse, and keep n tlog files
    @type ip: string
    @type port: int
    @type n: int > 0
    @type clusterId:string
    @param clusterId: must match cluster id of the node
    """
    if n < 1:
        raise ValueError("%i is not acceptable" % n)
    s = RCP.make_socket(ip, port)

    try:
        RCP._prologue(clusterId, s)
        cmd  = RCP._int_to(RCP._COLLAPSE_TLOGS | RCP._MAGIC)
        cmd += RCP._int_to(n)
        s.send(cmd)
        RCP.check_error_code(s)
        collapse_count = RCP._receive_int(s)
        logging.debug("collapse_count = %i", collapse_count)
        for i in range(collapse_count):
            logging.debug("i=%i", i)
            RCP.check_error_code(s)
            took = RCP._receive_int64(s)
            logging.info("took %i", took)
    finally:
        s.close()

def downloadDb(ip, port, clusterId, location):
    s = RCP.make_socket(ip, port)

    try:
        with open(location,'w+b') as db_file:
            RCP._prologue(clusterId, s)
            cmd  = RCP._int_to(RCP._DOWNLOAD_DB | RCP._MAGIC)
            s.send(cmd)
            RCP.check_error_code(s)
            db_size = RCP._receive_int64(s)
            while (db_size > 0 ) :
                chunkSize = min(4*1024, db_size)
                chunk = RCP._receive_all(s, chunkSize)
                db_size -= len(chunk)
                db_file.write(chunk)
    finally:
        s.close()

def _simple_cmd(ip,port,clusterId, code):
   s = RCP.make_socket(ip, port)
   RCP._prologue(clusterId, s)
   cmd = RCP._int_to(code | RCP._MAGIC)
   s.send(cmd)
   RCP.check_error_code(s)

def optimizeDb(ip, port, clusterId):
    _simple_cmd(ip,port,clusterId, RCP._OPTIMIZE_DB)

def defragDb(ip,port,clusterId):
    _simple_cmd(ip,port,clusterId, RCP._DEFRAG_DB)

def dropMaster(ip,port,clusterId):
    _simple_cmd(ip,port,clusterId, RCP._DROP_MASTER)

def setInterval(cluster_id, ip, port, pub_start, pub_end, priv_start, priv_end):
    s = RCP.make_socket(ip,port)
    try:
        RCP._prologue(cluster_id, s)
        cmd = RCP._int_to(RCP._COLLAPSE_TLOGS | RCP._MAGIC)
        cmd += RCP._string_option_to (pub_start)
        cmd += RCP._string_option_to (pub_end)
        cmd += RCP._string_option_to (priv_start)
        cmd += RCP._string_option_to (priv_end)
        s.send(cmd)
        RCP.check_error_code(s)
    finally:
        s.close()
