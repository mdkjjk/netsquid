import netsquid as ns
import numpy as np
from matplotlib import pyplot

from blueprint.base_configs import StackNetworkConfig
from blueprint.links.depolarise import DepolariseLinkConfig
from blueprint.network_builder import NetworkBuilder
from network_generation import create_2_node_network
from protocols import AliceProtocol, BobProtocol

ns.set_qstate_formalism(ns.QFormalism.DM)
builder = NetworkBuilder()


def run_simulation(cfg: StackNetworkConfig) -> float:
    network = builder.build(cfg)

    alice = AliceProtocol(network.get_protocol_context("Alice"))
    bob = BobProtocol(network.get_protocol_context("Bob"))

    alice.start()
    bob.start()
    builder.protocol_controller.start_all()
    ns.sim_run()

    qubit_alice = network.nodes["Alice"].qdevice.peek(0)[0]
    qubit_bob = network.nodes["Bob"].qdevice.peek(0)[0]

    reference_state = ns.qubits.ketstates.b00
    fidelity = ns.qubits.qubitapi.fidelity([qubit_alice, qubit_bob], reference_state)
    builder.protocol_controller.stop_all()
    return fidelity


link_config = DepolariseLinkConfig.from_file("config.yaml")
link_fidelities = np.arange(0.5, 1, 0.1)
measured_fidelity = []
num_average = 100

for link_fidelity in link_fidelities:
    link_config.fidelity = link_fidelity
    config = create_2_node_network("depolarise", link_config)

    measure_list = [run_simulation(config) for _ in range(num_average)]
    measured_fidelity.append(np.average(measure_list))

pyplot.plot(link_fidelities, measured_fidelity)
pyplot.savefig("out.png")
