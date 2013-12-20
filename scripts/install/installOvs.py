#!/usr/bin/env python
import os
import sys
from optparse import OptionParser

if os.getegid() != 0:
    print 'This script should be executed as a user in the root group.'
    sys.exit(1)

parser = OptionParser(description='CloudFrames vRun Setup')
parser.add_option('--no-filesystems', dest='filesystems', action="store_false", default=True,
                  help="Don't create partitions and filesystems")
(options, args) = parser.parse_args()

if options.filesystems:
    # Create partitions on HDD
    os.system('parted /dev/sdb -s mklabel gpt')
    os.system('parted /dev/sdb -s mkpart backendfs 2MB 90%')
    os.system('parted /dev/sdb -s mkpart distribfs 90% 100%')
    os.system('mkfs.ext4 /dev/sdb1 -L backendfs')
    os.system('mkfs.ext4 /dev/sdb2 -L distribfs')

    #Create partitions on SSD
    os.system('parted /dev/sdc -s mklabel gpt')
    os.system('parted /dev/sdc -s mkpart cache 2MB 50%')
    os.system('parted /dev/sdc -s mkpart db 50% 75%')
    os.system('parted /dev/sdc -s mkpart mdpath 75% 100%')
    os.system('mkfs.ext4 /dev/sdc1 -L cache')
    os.system('mkfs.ext4 /dev/sdc2 -L db')
    os.system('mkfs.ext4 /dev/sdc3 -L mdpath')
    os.system('mkdir /mnt/db')
    os.system('mkdir /mnt/cache')
    os.system('mkdir /mnt/md')
    os.system('mkdir /mnt/bfs')
    os.system('mkdir /mnt/dfs')

    # Add content to fstab
    fstab_content = """
# BEGIN Open vStorage
LABEL=db        /mnt/db    ext4    defaults,nobootwait,noatime,discard    0    2
LABEL=cache     /mnt/cache ext4    defaults,nobootwait,noatime,discard    0    2
LABEL=mdpath    /mnt/md    ext4    defaults,nobootwait,noatime,discard    0    2
LABEL=backendfs /mnt/bfs   ext4    defaults,nobootwait,noatime,discard    0    2
LABEL=distribfs /mnt/dfs   ext4    defaults,nobootwait,noatime,discard    0    2
# END Open vStorage
"""
    must_update = False
    with open('/etc/fstab', 'r') as fstab:
        contents = fstab.read()
        if not '# BEGIN Open vStorage' in contents:
            contents += '\n'
            contents += fstab_content
            must_update = True
    if must_update:
        with open('/etc/fstab', 'w') as fstab:
            fstab.write(contents)

# Mount all filesystems
os.system('mountall')

supported_quality_levels = ['unstable','test','stable']
quality_level = raw_input('Enter qualitylevel to install from %s: '%supported_quality_levels)
if not quality_level in supported_quality_levels:
    raise ValueError('Please specify correct qualitylevel, one of %s'%supported_quality_levels)

# Install all software components
os.system('apt-get -y install python-pip')
os.system('pip install https://bitbucket.org/jumpscale/jumpscale_core/get/default.zip')
os.system('jpackage_update')

jp_openvstorage_blobstor = """
[jp_openvstorage]
ftp = ftp://10.100.129.101
http = http://10.100.129.101/ovs-blobstore
namespace = jpackages
localpath =
type = httpftp
"""

jp_openvstorage_repo = """
[openvstorage]
metadatafromtgz = 0
qualitylevel = %(qualityLevel)s
metadatadownload = http://10.100.129.101/ovs-metadata
metadataupload = file://opt/jumpscale/var/jpackages/metatars
bitbucketaccount = openvstorage
bitbucketreponame = jp_openvstorage
blobstorremote = jp_openvstorage
blobstorlocal = jpackages_local
"""%{'qualityLevel': quality_level}

blobstor_config = open('/opt/jumpscale/cfg/jsconfig/blobstor.cfg', 'a')
blobstor_config.write(jp_openvstorage_blobstor)
blobstor_config.close()

jp_sources_config = open('/opt/jumpscale/cfg/jpackages/sources.cfg', 'a')
jp_sources_config.write(jp_openvstorage_repo)
jp_sources_config.close()

os.system('jpackage_update')
os.system('jpackage_install -n core')
os.system('jpackage_install -n openvstorage')

