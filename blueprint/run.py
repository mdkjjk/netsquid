from __future__ import annotations

import typing
from typing import Dict

import netsquid as ns

from blueprint.clinks.default import DefaultCLinkBuilder
from blueprint.clinks.instant import InstantCLinkBuilder
from netsquid_magic.models.depolarise import DepolariseLinkBuilder
from netsquid_magic.models.heralded_single_click import HeraldedSingleClickLinkBuilder
from netsquid_magic.models.heralded_double_click import HeraldedDoubleClickLinkBuilder
from blueprint.links.nv import NVLinkBuilder
from netsquid_magic.models.perfect import PerfectLinkBuilder
from blueprint.network_builder import NetworkBuilder
from blueprint.protocol_base import BlueprintProtocol
from blueprint.qdevices.generic import GenericQDeviceBuilder
from blueprint.qdevices.nv import NVQDeviceBuilder
from blueprint.scheduler.fifo import FIFOScheduleBuilder
from blueprint.scheduler.static import StaticScheduleBuilder

if typing.TYPE_CHECKING:
    from blueprint.network import Network


def get_default_builder() -> NetworkBuilder:
    builder = NetworkBuilder()
    # Default qdevice models registration
    builder.register_qdevice("generic", GenericQDeviceBuilder)
    builder.register_qdevice("nv", NVQDeviceBuilder)

    # default link models registration
    builder.register_link("perfect", PerfectLinkBuilder)
    builder.register_link("depolarise", DepolariseLinkBuilder)
    builder.register_link("heralded-single-click", HeraldedSingleClickLinkBuilder)
    builder.register_link("heralded-double-click", HeraldedDoubleClickLinkBuilder)
    builder.register_link("nv", NVLinkBuilder)

    # default clink models registration
    builder.register_clink("instant", InstantCLinkBuilder)
    builder.register_clink("default", DefaultCLinkBuilder)

    # default schedulers
    builder.register_scheduler("static", StaticScheduleBuilder)
    builder.register_scheduler("fifo", FIFOScheduleBuilder)

    return builder


def run(network: Network, protocols: Dict[str, BlueprintProtocol]):
    # start all protocols
    network.start()
    for node_name, prot in protocols.items():
        context = network.get_protocol_context(node_name)
        prot.set_context(context)
        prot.start()

    sim_stats = ns.sim_run()

    # stop all protocols
    network.stop()
    for node_name, prot in protocols.items():
        prot.stop()

    return sim_stats

