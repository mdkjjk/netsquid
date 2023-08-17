from __future__ import annotations

from typing import Dict, Type

from netsquid.components import Port
from netsquid_magic.link_layer import MagicLinkLayerProtocolWithSignaling
from netsquid_netbuilder.base_configs import StackNetworkConfig
from netsquid_netbuilder.builder.builder_utils import create_connection_ports
from netsquid_netbuilder.builder.metro_hub import HubBuilder
from netsquid_netbuilder.builder.repeater_chain import ChainBuilder
from netsquid_netbuilder.logger import LogManager
from netsquid_netbuilder.modules.clinks.interface import ICLinkBuilder, ICLinkConfig
from netsquid_netbuilder.modules.links.interface import ILinkBuilder, ILinkConfig
from netsquid_netbuilder.modules.qdevices.interface import IQDeviceBuilder
from netsquid_netbuilder.modules.scheduler.interface import IScheduleBuilder
from netsquid_netbuilder.network import Network

from squidasm.sim.stack.egp import EgpProtocol
from squidasm.sim.stack.stack import ProcessingNode


class NetworkBuilder:
    def __init__(self):
        self.protocol_controller = ProtocolController()
        self.node_builder = NodeBuilder()
        self.clink_builder = ClassicalConnectionBuilder()
        self.link_builder = LinkBuilder(self.protocol_controller)
        self.egp_builder = EGPBuilder(self.protocol_controller)
        self.hub_builder = HubBuilder(self.protocol_controller)
        self.chain_builder = ChainBuilder(self.protocol_controller)
        self._logger = LogManager.get_stack_logger(self.__class__.__name__)

    def register_qdevice(self, key: str, builder: Type[IQDeviceBuilder]):
        self.node_builder.register(key, builder)
        self.chain_builder.register_qdevice(key, builder)

    def register_link(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builder.register(key, builder, config)
        self.hub_builder.register(key, builder, config)
        self.chain_builder.register_link(key, builder, config)

    def register_clink(
        self, key: str, builder: Type[ICLinkBuilder], config: Type[ICLinkConfig]
    ):
        self.clink_builder.register(key, builder, config)
        self.hub_builder.register_clink(key, builder, config)
        self.chain_builder.register_clink(key, builder, config)

    def register_scheduler(self, key: str, builder: Type[IScheduleBuilder]):
        self.hub_builder.register_scheduler(key, builder)

    def build(self, config: StackNetworkConfig, hacky_is_squidasm_flag=True) -> Network:
        self.hub_builder.set_configs(config.hubs)
        self.chain_builder.set_configs(config.repeater_chains)

        network = Network()
        network.hubs = self.hub_builder.create_metro_hub_objects()
        network.chains = self.chain_builder.create_chain_objects(network.hubs)

        network.end_nodes = self.node_builder.build(
            config, hacky_is_squidasm_flag=hacky_is_squidasm_flag
        )
        self.hub_builder.register_end_nodes_to_hub(network)
        self.hub_builder.build_hub_nodes(network)
        self.chain_builder.build_repeater_nodes(network)

        network.node_name_id_mapping = self.create_node_name_id_mapping(network)

        network.ports = self.clink_builder.build(
            config, network, hacky_is_squidasm_flag=hacky_is_squidasm_flag
        )
        network.ports.update(
            self.hub_builder.build_classical_connections(
                network, hacky_is_squidasm_flag=hacky_is_squidasm_flag
            )
        )
        network.ports.update(
            self.chain_builder.build_classical_connections(
                network,
                hacky_is_squidasm_flag=hacky_is_squidasm_flag,
            )
        )

        network.links = self.link_builder.build(config, network.end_nodes)
        network.links.update(self.hub_builder.build_links(network))
        network.links.update(self.chain_builder.build_links(network))

        network.schedulers = self.hub_builder.build_schedule(network)

        network.egp = self.egp_builder.build(network)

        network._protocol_controller = self.protocol_controller

        return network

    @staticmethod
    def create_node_name_id_mapping(network: Network) -> Dict[str, int]:
        mapping = {node_name: node.ID for node_name, node in network.end_nodes.items()}
        for chain in network.chains.values():
            mapping.update(
                {
                    node_name: node.ID
                    for node_name, node in chain.repeater_nodes_dict.items()
                }
            )
        return mapping


class NodeBuilder:
    def __init__(self):
        self.qdevice_builders: Dict[str, Type[IQDeviceBuilder]] = {}

    def register(self, key: str, builder: Type[IQDeviceBuilder]):
        self.qdevice_builders[key] = builder

    def build(
        self, config: StackNetworkConfig, hacky_is_squidasm_flag=True
    ) -> Dict[str, ProcessingNode]:
        nodes = {}
        for node_config in config.stacks:
            if node_config.qdevice_typ not in self.qdevice_builders.keys():
                # TODO improve exception
                raise Exception(
                    f"No model of type: {node_config.qdevice_typ} registered"
                )

            builder = self.qdevice_builders[node_config.qdevice_typ]
            qdevice = builder.build(
                f"qdevice_{node_config.name}", qdevice_cfg=node_config.qdevice_cfg
            )

            # TODO ProcessingNode is a very SquidASM centric object
            nodes[node_config.name] = ProcessingNode(
                node_config.name,
                qdevice=qdevice,
                qdevice_type=node_config.qdevice_typ,
                hacky_is_squidasm_flag=hacky_is_squidasm_flag,
            )
        return nodes


class ClassicalConnectionBuilder:
    def __init__(self):
        self.clink_builders: Dict[str, Type[ICLinkBuilder]] = {}
        self.clink_configs: Dict[str, Type[ICLinkConfig]] = {}

    def register(
        self, key: str, builder: Type[ICLinkBuilder], config: Type[ICLinkConfig]
    ):
        self.clink_builders[key] = builder
        self.clink_configs[key] = config

    def build(
        self, config: StackNetworkConfig, network: Network, hacky_is_squidasm_flag
    ) -> Dict[(str, str), Port]:
        nodes = network.end_nodes
        ports = {}
        if config.clinks is None:
            return {}
        for clink in config.clinks:
            s1 = nodes[clink.stack1]
            s2 = nodes[clink.stack2]
            clink_builder = self.clink_builders[clink.typ]
            connection = clink_builder.build(s1, s2, link_cfg=clink.cfg)

            ports.update(
                create_connection_ports(s1, s2, connection, port_prefix="host")
            )

            if hacky_is_squidasm_flag:
                s1.register_peer(s2.ID)
                s2.register_peer(s1.ID)
                connection_qnos = clink_builder.build(s1, s2, link_cfg=clink.cfg)

                s1.qnos_peer_port(s2.ID).connect(connection_qnos.port_A)
                s2.qnos_peer_port(s1.ID).connect(connection_qnos.port_B)
        return ports


class LinkBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller
        self.link_builders: Dict[str, Type[ILinkBuilder]] = {}
        self.link_configs: Dict[str, Type[ILinkConfig]] = {}

    def register(
        self, key: str, builder: Type[ILinkBuilder], config: Type[ILinkConfig]
    ):
        self.link_builders[key] = builder
        self.link_configs[key] = config

    def build(
        self, config: StackNetworkConfig, nodes: Dict[str, ProcessingNode]
    ) -> Dict[(str, str), MagicLinkLayerProtocolWithSignaling]:
        link_dict = {}
        if config.links is None:
            return {}
        for link in config.links:
            node1 = nodes[link.stack1]
            node2 = nodes[link.stack2]
            if link.typ not in self.link_builders.keys():
                # TODO improve exception
                raise Exception(f"No model of type: {link.typ} registered")

            builder = self.link_builders[link.typ]
            link_prot = builder.build(node1, node2, link.cfg)
            self.protocol_controller.register(link_prot)
            link_dict[(node1.name, node2.name)] = link_prot
            link_dict[(node2.name, node1.name)] = link_prot

        return link_dict


class EGPBuilder:
    def __init__(self, protocol_controller: ProtocolController):
        self.protocol_controller = protocol_controller

    def build(self, network: Network) -> Dict[(str, str), EgpProtocol]:

        egp_dict = {}
        for id_tuple, link_layer in network.links.items():
            node_name, peer_node_name = id_tuple
            if (
                network.find_role(node_name) is network.Role.END_NODE
                and network.find_role(peer_node_name) is network.Role.END_NODE
            ):
                node = network.end_nodes[node_name]
                egp = EgpProtocol(node, link_layer)
                egp_dict[(node_name, peer_node_name)] = egp
                self.protocol_controller.register(egp)
        return egp_dict


class ProtocolController:
    def __init__(self):
        self._registry = []

    def register(self, obj: object):
        assert callable(getattr(obj, "start", None))
        assert callable(getattr(obj, "stop", None))
        self._registry.append(obj)

    def start_all(self):
        for obj in self._registry:
            obj.start()

    def stop_all(self):
        for obj in self._registry:
            obj.stop()
