import math

from netqasm.sdk import EPRSocket
from netqasm.sdk.connection import DebugConnection
from netqasm.sdk.external import NetQASMConnection, Socket
from netqasm.sdk.compiling import NVSubroutineCompiler


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={'alpha': 0, 'beta': 0, 'theta1': 0, 'theta2': 0, 'r1': 0, 'r2': 0},
):
    alpha, beta, theta1, r1 = inputs['alpha'], inputs['beta'], inputs['theta1'], inputs['r1']

    socket = Socket("client", "server")

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("server", min_fidelity=75)

    # Initialize the connection
    kwargs = {
        "app_name": "client",
        "log_config": None,
        "epr_sockets": [epr_socket],
        "compiler": NVSubroutineCompiler,
        "return_arrays": False,
    }

    # Initialize the connection
    if not app_config["debug"]:
        client = NetQASMConnection(**kwargs, addr=app_config["addr"], port=app_config["port"],
                                   dev=app_config["dev"])
    else:
        DebugConnection.node_ids["server"] = 0
        DebugConnection.node_ids["client"] = 1
        client = DebugConnection(**kwargs)

    with client:
        # Create EPR pairs
        epr = epr_socket.create()[0]

        epr.rot_Z(angle=theta1)
        epr.H()

        p1 = epr.measure(store_array=False)
        p1 = p1 if not app_config["debug"] else 0
        client.flush()

        p1 = int(p1)
        p1 = p1 if not app_config["debug"] else 0
        delta1 = alpha - theta1 + (p1 + r1) * math.pi

        socket.send(str(delta1))

        m1 = int(socket.recv())
        delta2 = math.pow(-1, (r1 + m1)) * beta

        socket.send(str(delta2))

    return {'p1': p1}


if __name__ == "__main__":
    main()
