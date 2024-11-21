"""
IPAM Syncronisation
"""
from application import logger
from application.modules.netbox.netbox import SyncNetbox
from application.models.host import Host
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, MofNCompleteColumn


class SyncIPAM(SyncNetbox):
    """
    IP Syncer
    """
    console = None

    @staticmethod
    def get_field_config():
        """
        Return Fields needed for Devices
        """
        translation = {
        }
        form_rules = {
        }

        return translation, form_rules

    def sync_ips(self):
        """
        Sync IP Addresses
        """
        # Get current IPs
        current_ips = self.nb.ipam.ip_addresses

        object_filter = self.config['settings'].get(self.name, {}).get('filter')
        db_objects = Host.objects_by_filter(object_filter)
        total = db_objects.count()
        with Progress(SpinnerColumn(),
                      MofNCompleteColumn(),
                      *Progress.get_default_columns(),
                      TimeElapsedColumn()) as progress:
            self.console = progress.console.print
            task1 = progress.add_task("Updating IPs", total=total)
            for db_object in db_objects:
                hostname = db_object.hostname

                self.console(f'Handling: {hostname}')

                all_attributes = self.get_host_attributes(db_object, 'netbox_hostattribute')
                if not all_attributes:
                    progress.advance(task1)
                    continue
                cfg_ips = self.get_host_data(db_object, all_attributes['all'])

                if cfg_ips.get('ignore_ip'):
                    progress.advance(task1)
                    continue

                logger.debug(f"Working with {cfg_ips}")
                address = cfg_ips['fields']['address']
                if not address:
                    continue
                ip_query = {
                    'address': address,
                    'assigned_object': cfg_ips['fields']['assigned_object_id'],
                }
                logger.debug(f"IPAM IPS Filter Query: {ip_query}")
                if ip := current_ips.get(**ip_query):
                    # Update
                    if payload := self.get_update_keys(ip, cfg_ips):
                        self.console(f"* Update IP: for {hostname} {payload}")
                        ip.update(payload)
                    else:
                        self.console("* Netbox already up to date")
                else:
                    ### Create
                    self.console(f" * Create IP for {hostname}")
                    payload = self.get_update_keys(False, cfg_ips)
                    logger.debug(f"Create Payload: {payload}")
                    ip = self.nb.ipam.ip_addresses.create(payload)

                progress.advance(task1)
