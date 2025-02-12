#!/usr/bin/env python3
"""Sync VMware Vsphere Custom Attributes"""
#pylint: disable=logging-fstring-interpolation

from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, MofNCompleteColumn

try:
    from pyVmomi import vim
except ImportError:
    pass

from syncerapi.v1 import (
    Host,
)

from syncerapi.v1.inventory import (
    run_inventory,
)

from application import logger
from application import app
from application.modules.vmware.vmware import VMWareVcenterPlugin


class VMwareCustomAttributesPlugin(VMWareVcenterPlugin):
    """
    VMware Custom Attributes
    """
    console = None

    def get_vm_attributes(self, vm, content):
        """
        Prepare Attributes
        """
        attributes = {
            "name": vm.name,
            "power_state": vm.runtime.powerState,
        }

        if vm.guest:
            attributes.update({
                "ip_address": vm.guest.ipAddress,
                "hostname": vm.guest.hostName,
                "full_name": vm.guest.guestFullName,
                "tools_status": vm.guest.toolsStatus,
            })
        if vm.config:
            attributes.update({
                "cpu_count": vm.config.hardware.numCPU,
                "memory_mb": vm.config.hardware.memoryMB,
                "guest_os": vm.config.guestFullName,
                "uuid": vm.config.uuid,
                "guest_id": vm.config.guestId,
                "annotation": vm.config.annotation,
                "hw_device": vm.config.hardware.device,
            })

        if vm.runtime:
            attributes.update({
                 "power_state": vm.runtime.powerState,
                 "runtime_host": vm.runtime.host,
                 "boot_time": vm.runtime.bootTime,
            })

        if vm.network:
            attributes['network'] = vm.network

        if vm.datastore:
            attributes['datastore'] = vm.datastore

        if vm.customValue:
            for custom_field in vm.customValue:
                field_key = custom_field.key
                field_name = next(
                    (f.name for f in content.customFieldsManager.field if f.key == field_key),
                    f"custom_{field_key}"
                )
                attributes[field_name] = custom_field.value
        return attributes


    def get_current_attributes(self):
        """
        Return list of all Objects
        and their Attributes
        """
        content = self.vcenter.RetrieveContent()
        container = content.viewManager.CreateContainerView(content.rootFolder,
                                                            [vim.VirtualMachine], True)
        data = [self.get_vm_attributes(x, content) for x in container.view]
        container.Destroy()
        return data


    def export_attributes(self):
        """
        Export Custom Attributes
        """
        self.connect()
        current_attributes = {x['name']:x for x in self.get_current_attributes()}
        print(current_attributes)

        object_filter = self.config['settings'].get(self.name, {}).get('filter')
        db_objects = Host.objects_by_filter(object_filter)
        total = db_objects.count()
        with Progress(SpinnerColumn(),
                      MofNCompleteColumn(),
                      *Progress.get_default_columns(),
                      TimeElapsedColumn()) as progress:
            self.console = progress.console.print
            task1 = progress.add_task("Updating Attributes", total=total)
            hostname = None
            for db_host in db_objects:
                try:
                    hostname = db_host.hostname
                    all_attributes = self.get_host_attributes(db_host, 'vmware_vcenter')
                    if not all_attributes:
                        progress.advance(task1)
                        continue
                    custom_rules = self.get_host_data(db_host, all_attributes['all'])
                    if not custom_rules:
                        progress.advance(task1)
                        continue

                    self.console(f" * Work on {hostname}")
                    logger.debug(f"{hostname}: {custom_rules}")
                except Exception as error:
                    if self.debug:
                        raise
                    self.log_details.append((f'export_error {hostname}', str(error)))
                    self.console(f" Error in process: {error}")
                progress.advance(task1)


    def inventorize_attributes(self):
        """
        Inventorize Custom Attributes
        """
        self.connect()
        run_inventory(self.config, [(x['name'], x) for x in self.get_current_attributes()])
