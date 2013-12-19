# license see http://www.openvstorage.com/licenses/opensource/
"""
VMachine module
"""
import time
import logging

from celery import group
from ovs.celery import celery
from ovs.dal.hybrids.pmachine import PMachine
from ovs.dal.hybrids.vmachine import VMachine
from ovs.dal.lists.vmachinelist import VMachineList
from ovs.dal.lists.vdisklist import VDiskList
from ovs.dal.lists.volumestoragerouterlist import VolumeStorageRouterList
from ovs.extensions.hypervisor.factory import Factory
from ovs.lib.vdisk import VDiskController
from ovs.lib.messaging import MessageController


class VMachineController(object):

    """
    Contains all BLL related to VMachines
    """

    @staticmethod
    @celery.task(name='ovs.machine.create_from_template')
    def create_from_template(name, machineguid, pmachineguid, **kwargs):
        """
        Create a new vmachine using an existing vmachine template

        @param machineguid: guid of the template vmachine
        @param name: name of new vmachine
        @param pmachineguid: guid of hypervisor to create new vmachine on
        @return: guid of the newly created vmachine | False on any failure
        """

        template_vm = VMachine(machineguid)
        if not template_vm.is_vtemplate:
            return False

        target_pm = PMachine(pmachineguid)

        nr_of_vpools = 0
        for disk in template_vm.vdisks:
            vpool = disk.vpool
            nr_of_vpools += 1
        if nr_of_vpools <> 1:
            raise RuntimeError('Only 1 vpool supported on template disk(s) - {0} found!'.format(nr_of_vpools))

        if not template_vm.pmachine.hvtype == target_pm.hvtype:
            raise RuntimeError('Source and target hypervisor not identical')

        for vsr in vpool.vsrs:
            if vsr.serving_vmachine.pmachine.guid == target_pm.guid:
                break
            raise RuntimeError('Volume not served on target hypervisor')

        source_hv = Factory.get(template_vm.pmachine)
        target_hv = Factory.get(target_pm)
        if not source_hv.is_datastore_available(vsr.ip, vsr.mountpoint):
            raise RuntimeError('Datastore unavailable on source hypervisor')
        if not target_hv.is_datastore_available(vsr.ip, vsr.mountpoint):
            raise RuntimeError('Datastore unavailable on target hypervisor')

        # @todo verify all disks can be cloned on target
        # @todo ie vpool is available on both hypervisors
        # @todo if so, continue

        new_vm = VMachine()
        for item in template_vm._blueprint.keys():
            setattr(new_vm, item, getattr(template_vm, item))
        new_vm.name = name
        new_vm.is_vtemplate = False
        new_vm.devicename = '{}/{}.vmx'.format(name.replace(' ', '_'), name.replace(' ', '_'))
        new_vm.save()

        disk_tasks = []
        disks_by_order = sorted(template_vm.vdisks, key=lambda x: x.order)
        for disk in disks_by_order:
            prefix = '%s-clone' % disk.name
            clone_task = VDiskController.create_from_template.s(
                diskguid=disk.guid,
                devicename=prefix,
                location=new_vm.name,
                machineguid=new_vm.guid)
            disk_tasks.append(clone_task)
        clone_disk_tasks = group(t for t in disk_tasks)
        group_result = clone_disk_tasks()
        while not group_result.ready():
            time.sleep(1)
        if group_result.successful():
            disks = group_result.join()
        else:
            for task_result in group_result:
                if task_result.successfull():
                    VDiskController.delete(
                        diskguid=task_result.get()['diskguid'])
            new_vm.delete()
            return group_result.successful()

        # @todo: temporary fix to provide vmdsk descriptor file

        source_vm = source_hv.get_vm_object(template_vm.hypervisorid)
        if not source_vm:
            raise RuntimeError(
                'VM with key reference %s not found' % template_vm.hypervisorid)

        provision_machine_task = target_hv.create_vm_from_template.s(target_hv,
            name, source_vm, disks, esxhost=None, wait=True)
        provision_machine_task.link_error(
           VMachineController.delete.s(machineguid=new_vm.guid))
        result = provision_machine_task()

        new_vm.hypervisorid = result
        new_vm.save()
        return new_vm.guid

    @staticmethod
    @celery.task(name='ovs.machine.create_from_voldrv')
    def create_from_voldrv(name):
        """
        This method will create a vmachine based on a given vmx file
        """
        name = name.strip('/')
        if name.endswith('.vmx'):
            vmachine = VMachineList.get_by_devicename(name)
            if not vmachine:
                vmachine = VMachine()
            vmachine.devicename = name
            vmachine.status = 'CREATED'
            vmachine.save()

    @staticmethod
    @celery.task(name='ovs.machine.clone')
    def clone(machineguid, timestamp, name, **kwargs):
        """
        Clone a vmachine using the disk snapshot based on a snapshot timestamp

        @param machineguid: guid of the machine to clone
        @param timestamp: timestamp of the disk snapshots to use for the clone
        @param name: name for the new machine
        """

        _ = kwargs
        machine = VMachine(machineguid)

        disks = {}
        for snapshot in machine.snapshots:
            if snapshot['timestamp'] == timestamp:
                for diskguid, snapshotguid in snapshot['snapshots'].iteritems():
                    disks[diskguid] = snapshotguid

        new_machine = VMachine()
        for item in machine._blueprint.keys():
            setattr(new_machine, item, getattr(machine, item))
        new_machine.name = name
        new_machine.save()

        disk_tasks = []
        disks_by_order = sorted(machine.vdisks, key=lambda x: x.order)
        for currentDisk in disks_by_order:
            if machine.template and currentDisk.templatesnapshot:
                snapshotid = currentDisk.templatesnapshot
            else:
                snapshotid = disks[currentDisk.guid]
            prefix = '%s-clone' % currentDisk.name
            clone_task = VDiskController.clone.s(diskguid=currentDisk.guid,
                                                 snapshotid=snapshotid,
                                                 devicename=prefix,
                                                 location=new_machine.name,
                                                 machineguid=new_machine.guid)
            disk_tasks.append(clone_task)
        clone_disk_tasks = group(t for t in disk_tasks)
        group_result = clone_disk_tasks()
        while not group_result.ready():
            time.sleep(1)
        if group_result.successful():
            disks = group_result.join()
        else:
            for task_result in group_result:
                if task_result.successfull():
                    VDiskController.delete(
                        diskguid=task_result.get()['diskguid'])
            new_machine.delete()
            return group_result.successful()

        hv = Factory.get(machine.pmachine)
        provision_machine_task = hv.clone_vm.s(
            hv, machine.hypervisorid, name, disks, None, True)
        provision_machine_task.link_error(
            VMachineController.delete.s(machineguid=new_machine.guid))
        result = provision_machine_task()

        new_machine.hypervisorid = result.get()
        new_machine.save()
        return new_machine.guid

    @staticmethod
    @celery.task(name='ovs.machine.delete')
    def delete(machineguid, **kwargs):
        """
        Delete a vmachine

        @param machineguid: guid of the machine
        """
        _ = kwargs
        machine = VMachine(machineguid)

        clean_dal = False
        if machine.pmachine:
            hv = Factory.get(machine.pmachine)
            delete_vmachine_task = hv.delete_vm.s(
                hv, machine.hypervisorid, None, True)
            delete_vmachine_task()
            clean_dal = True
        else:
            clean_dal = True

        if clean_dal:
            for disk in machine.vdisks:
                disk.delete()
            machine.delete()

        return True

    @staticmethod
    @celery.task(name='ovs.machine.delete_from_voldrv')
    def delete_from_voldrv(name):
        """
        This method will delete a vmachine based on the name of the vmx given
        """
        name = name.strip('/')
        if name.endswith('.vmx'):
            vm = VMachineList.get_by_devicename(name)
            if vm is not None:
                MessageController.fire(MessageController.Type.EVENT, {'type': 'vmachine_deleted',
                                                                      'metadata': {'name': vm.name}})
                vm.delete()

    @staticmethod
    @celery.task(name='ovs.machine.rename_from_voldrv')
    def rename_from_voldrv(old_name, new_name, vsrid):
        """
        This machine will handle the rename of a vmx file
        """
        old_name = old_name.strip('/')
        new_name = new_name.strip('/')
        # @TODO: When implementing more hypervisors, move part of code to hypervisor factory
        # vsr = VolumeStorageRouterList.get_by_vsrid(vsrid)
        # hypervisor = Factory.get(vsr.serving_vmachine.pmachine)
        # scenario = hypervisor.get_scenario(old_name, new_name)
        # if scenario == 'RENAME': f00bar
        # if scenario == 'UPDATED': f00bar
        # > This way, this piece of code is hypervisor agnostic
        if old_name.endswith('.vmx') and new_name.endswith('.vmx'):
            # Most likely a change from path. Updaing path
            vm = VMachineList.get_by_devicename(old_name)
            if vm is not None:
                vm.devicename = new_name
                vm.save()
        elif old_name.endswith('.vmx~') and new_name.endswith('.vmx'):
            vm = VMachineList.get_by_devicename(new_name)
            # The configuration has been updated (which happens in a tempfile), start a sync
            if vm is not None:
                try:
                    VMachineController.sync_with_hypervisor(vm.guid, vsrid)
                    vm.status = 'SYNC'
                except:
                    vm.status = 'SYNC_NOK'
                vm.save()


    @staticmethod
    @celery.task(name='ovs.machine.set_as_template')
    def set_as_template(machineguid, **kwargs):
        """
        Set a vmachine as template

        @param machineguid: guid of the machine
        @return: vmachine template conversion successful: True|False
        """
        # Do some magic on the storage layer?
        # This is most likely required as extra security measure
        # Suppose the template is set back to a real machine
        # it can be deleted within vmware which should be blocked.
        # This might also require a storagerouter internal check
        # to be implemented to discourage volumes from being deleted
        # when clones were made from it.

        vmachine = VMachine(machineguid)
        tasks = []

        for disk in vmachine.vdisks:
            t = VDiskController.set_as_template.s(diskguid=disk.guid)
            tasks.append(t)
        set_as_template_vmachine_wf = group(t for t in tasks)
        group_result = set_as_template_vmachine_wf()
        while not group_result.ready():
            time.sleep(1)

        if group_result.successful():
            group_result.join()
            for task_result in group_result:
                if not task_result.successful():
                    vmachine.is_vtemplate = False
                    break
            vmachine.is_vtemplate = True
        else:
            vmachine.is_vtemplate = False

        vmachine.save()

        return group_result.successful()

    @staticmethod
    @celery.task(name='ovs.machine.rollback')
    def rollback(machineguid, timestamp, **kwargs):
        """
        Rolls back a VM based on a given disk snapshot timestamp
        """
        _ = machineguid, timestamp, kwargs

    @staticmethod
    @celery.task(name='ovs.machine.snapshot')
    def snapshot(machineguid, label=None, is_consistent=False, timestamp=None, subtasks=True):
        """
        Snapshot VMachine disks

        @param machineguid: guid of the machine
        @param label: label to give the snapshots
        @param is_consistent: flag indicating the snapshot was consistent or not
        @param timestamp: override timestamp, if required. Should be a unix timestamp
        """

        timestamp = timestamp if timestamp is not None else time.time()
        timestamp = str(int(float(timestamp)))

        metadata = {'label': label,
                    'is_consistent': is_consistent,
                    'timestamp': timestamp,
                    'machineguid': machineguid}
        machine = VMachine(machineguid)
        if subtasks:
            tasks = []
            for disk in machine.vdisks:
                t = VDiskController.create_snapshot.s(diskguid=disk.guid,
                                                      metadata=metadata)
                t.link_error(VDiskController.delete_snapshot.s())
                tasks.append(t)
            snapshot_vmachine_wf = group(t for t in tasks)
            snapshot_vmachine_wf()
        else:
            for disk in machine.vdisks:
                VDiskController.create_snapshot(diskguid=disk.guid,
                                                metadata=metadata)

    @staticmethod
    @celery.task(name='ovs.machine.sync_with_hypervisor')
    def sync_with_hypervisor(vmachineguid, vsrid=None):
        """
        Updates a given vmachine with data retreived from a given pmachine
        """
        vmachine = VMachine(vmachineguid)
        if vmachine.hypervisorid is not None and vmachine.pmachine is not None:
            # We have received a vmachine which is linked to a pmachine and has a hypervisorid.
            hypervisor = Factory.get(vmachine.pmachine)
            logging.info('Syncing vMachine (name {})'.format(vmachine.name))
            vm_object = hypervisor.get_vm_agnostic_object(vmid=vmachine.hypervisorid)
        elif vmachine.devicename is not None and vsrid is not None:
            # We don't have a pmachine or hypervisorid, we need to load the data via the
            # devicename and vsr.
            vsr = VolumeStorageRouterList.get_by_vsrid(vsrid)
            if vsr is None:
                raise RuntimeError('VolumeStorageRouter could not be found')
            vsa = vsr.serving_vmachine
            if vsa is None:
                raise RuntimeError('VolumeStorageRouter {} not linked to a VSA'.format(vsr.name))
            pmachine = vsa.pmachine
            if pmachine is None:
                raise RuntimeError('VSA {} not linked to a pMachine'.format(vsa.name))
            hypervisor = Factory.get(pmachine)
            vmachine.pmachine = pmachine
            vmachine.save()

            logging.info('Syncing vMachine (device {}, ip {}, mtpt {})'.format(vmachine.devicename,
                                                                               vsr.ip,
                                                                               vsr.mountpoint))
            vm_object = hypervisor.get_vm_object_by_devicename(devicename=vmachine.devicename,
                                                               ip=vsr.ip,
                                                               mountpoint=vsr.mountpoint)
        else:
            raise RuntimeError('Not enough information to sync vmachine')

        vdisks_synced = 0
        if vm_object is None:
            raise RuntimeError('Could not retreive hypervisor vmachine object')
        else:
            vmachine.name = vm_object['name']
            vmachine.hypervisorid = vm_object['id']
            vmachine.devicename = vm_object['backing']['filename']
            vmachine.save()
            # Updating and linking disks
            for disk in vm_object['disks']:
                vdisk = VDiskList.get_by_devicename(disk['filename'])
                if vdisk is not None:
                    vsr = VolumeStorageRouterList.get_by_vsrid(vdisk.vsrid)
                    if vsr is None:
                        raise RuntimeError('vDisk without VSR found')
                    datastore = vm_object['datastores'][disk['datastore']]
                    if datastore == '{}:{}'.format(vsr.ip, vsr.mountpoint):
                        vdisk.vmachine = vmachine
                        vdisk.name = disk['name']
                        vdisk.order = disk['order']
                        vdisk.save()
                        vdisks_synced += 1

        logging.info('Syncing vMachine finished (name {}, {} vdisks (re)linked)'.format(
            vmachine.name, vdisks_synced
        ))
