#!/usr/bin/env python3
"""
Get Hosts from a CMKv1 Instance
"""
import ast
import click
import requests
from mongoengine.errors import DoesNotExist
from application import app, log
from application.models.host import Host
from application.helpers.get_source import get_source_by_name


class DataGeter():
    """
    Get Data from CMK
    """

    def __init__(self, config):
        """
        Inital
        """
        self.log = log
        self.config = config
        self.source_id = str(config['_id'])
        self.source_name = config['name']

    def request(self, what, payload):
        """
        Generic function to contact the api
        """
        config = self.config
        config["action"] = what

        url = "{address}/check_mk/webapi.py" \
              "?action={action}&_username={username}" \
              "&_secret={password}&output_format=python&request_format=python".format(**config)

        if payload: # payload is not empty
            formated = ascii(payload).replace(" '", " u'")
            formated = formated.replace("{'", "{u'")
        else: # payload is empty
            formated = ascii(payload)

        response = requests.post(url, {"request": formated}, verify=False)
        return ast.literal_eval(response.text)


    def run(self):
        """Run Actual Job"""
        all_hosts = self.request("get_all_hosts", {})['result']
        found_hosts = []
        for hostname, _host_data in all_hosts.items():
            found_hosts.append(hostname)
            try:
                host = Host.objects.get(hostname=hostname)
                host.add_log('Found in Source')
            except DoesNotExist:
                host = Host()
                host.set_hostname(hostname)
                host.set_source(self.source_id, self.source_name)
                host.add_log("Inital Add")
            host.set_source_update()
            host.save()
        for host in Host.objects(source_id=self.source_id, available_on_source=True):
            if host.hostname not in found_hosts:
                host.set_source_not_found()
                host.save()


@app.cli.command('import_cmk-v1')
@click.argument("source")
def get_cmk_data(source):
    """Get All hosts from CMK and add them to db"""
    if source_config := get_source_by_name(source):
        getter = DataGeter(source_config)
        getter.run()
    else:
        print("Source not found")
