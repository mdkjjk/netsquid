from netqasm.sdk import Qubit, EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from netqasm.sdk.toolbox import set_qubit_state
from squidasm.sdk import NetSquidConnection


def main(track_lines=True, log_subroutines_dir=None, phi=0., theta=0.):

    # Create a socket to send classical information
    socket = Socket("alice", "bob", comm_log_dir=log_subroutines_dir)

    # Create a EPR socket for entanglement generation
    epr_socket = EPRSocket("bob")

    # Initialize the connection to the backend
    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=[epr_socket]
    )
    with alice:
        # Create a qubit to teleport
        q = Qubit(alice)
        set_qubit_state(q, phi, theta)

        # Create EPR pairs
        epr = epr_socket.create()[0]

        # Teleport
        q.cnot(epr)
        q.H()
        m1 = q.measure()
        m2 = epr.measure()

    # Send the correction information
    m1, m2 = int(m1), int(m2)
    msg = str((m1, m2))
    socket.send(msg)

    return {'m1': m1, 'm2': m2}


if __name__ == "__main__":
    main()