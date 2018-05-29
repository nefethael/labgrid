"""The usb_otg module provides support to switch USB OTG role """
import enum
import os

import attr

from ..exceptions import NoDriverFoundError
from ..protocol import CommandProtocol
from ..step import step

debugfspath = '/sys/kernel/debug'
authfmt = '/sys/bus/usb/devices/{}/authorized'

class OTGStatus(enum.Enum):
    unknown = 0
    gadget = 1
    host = 2


@attr.s(cmp=False)
class USBOTG(object):
    """The USBOTG class provides an easy to use interface to switch USB OTG role """
    target = attr.ib()
    iface = attr.ib(default="usb2", validator=attr.validators.instance_of(str))
    ctrl = attr.ib(default="ci_hdrc.0", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.status = OTGStatus.unknown

        self.command = self.target.get_active_driver( #pylint: disable=no-member
            CommandProtocol
        )
        if not self.command:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(CommandProtocol)
            )

        stdout, stderr, returncode = self.command.run('mount -t debugfs none {}'.format(debugfspath))
        if ((returncode != 0) and (returncode != 255)):
            raise OTGError("Cannot mount debugfs")


    @staticmethod
    def _otg_switch(shell, mode, ctrl):
        rolefile = '{fs}/{ctl}/role'.format(fs=debugfspath, ctl=ctrl)

        stdout, stderr, returncode = shell.run('ls {}'.format(rolefile))
        if returncode != 0:
            raise OTGError("Cannot access USB OTG role file")

        shell.run('echo {} > {}'.format(mode, rolefile))
        stdout, _, _ = shell.run('cat {}'.format(rolefile))
        if mode != stdout[0]:
            raise OTGError("Cannot set USB OTG role")

    @step()
    def set_host(self):	
        authfile = authfmt.format(self.iface)

        if self.status != OTGStatus.host:
            self._otg_switch(self.command, 'host', self.ctrl)

            # switch from gadget to host 
            _, _, exitcode = self.command.run('ls {}'.format(authfile))
            if exitcode == 0:
                # if it exists, check port is authorized
                self.command.run_check('echo 1 > {}'.format(authfile))

            self.status = OTGStatus.host


    @step()
    def set_gadget(self):
        authfile = authfmt.format(self.iface)

        if self.status != OTGStatus.gadget:
            # switch from host to gadget can hang if port is in use
            # we check for authorized file presence
            _, _, exitcode = self.command.run('ls {}'.format(authfile))
            if exitcode == 0:
                # if it exists, port is in host mode, poweroff
                self.command.run_check('echo 0 > {}'.format(authfile))

            self._otg_switch(self.command, 'gadget', self.ctrl)
            self.status = OTGStatus.gadget

@attr.s(cmp=False)
class OTGError(Exception):
    msg = attr.ib()

