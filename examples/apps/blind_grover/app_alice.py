import numpy as np

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import EPRSocket
from netqasm.sdk import ThreadSocket as Socket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def measXY(q, angle):
    """Measure qubit `q` in the XY-plane rotated by `angle`.
    Note: we use the convention that we rotate by +`angle` (not -`angle`).
    """
    q.rot_Z(angle=angle)
    q.H()
    return q.measure()


def teleport_state(epr_socket, theta):
    """Teleport a state Rz(theta)|+> to Bob.
    The resulting state on Bob's side is actually
    Rz(theta + m*pi) |+>, for Alice's measurement outcome `m`.
    """
    epr = epr_socket.create()[0]
    m = measXY(epr, theta)
    return m


def send_meas_cmd(socket, phi):
    """Tell Bob to measure the next qubit in angle `phi`.
    This effectively applies the operation H Rz(phi) on the logical input.
    """
    socket.send(str(phi))


def recv_meas_outcome(socket):
    """Receive the measurement outcome (0 or 1) of Bob's
    last measurement.
    """
    return int(socket.recv())


def get_phi_for_oracle(b0, b1):
    """Compute the angles `phi1` and `phi2` needed to simulate
    an oracle that only tags the input (b0, b1).
    """
    phi1 = np.pi / 2 - b0 * np.pi
    phi2 = (1 - (b0 ^ b1)) * np.pi
    return phi1, phi2


def main(
        track_lines=True,
        log_subroutines_dir=None,
        app_dir=None,
        b0=0,
        b1=0,
        r1=0,
        r2=0,
        theta1=0.0,
        theta2=0.0):

    socket = Socket("alice", "bob", comm_log_dir=log_subroutines_dir, track_lines=track_lines, app_dir=app_dir)
    epr_socket = EPRSocket("bob")

    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        log_subroutines_dir=log_subroutines_dir,
        app_dir=app_dir,
        epr_sockets=[epr_socket],
    )

    num_qubits = 4
    phi1, phi2 = get_phi_for_oracle(b0, b1)

    # Set theta0 and theta3 to 0.
    theta = [0 for _ in range(num_qubits)]
    theta[1] = theta1
    theta[2] = theta2

    with alice:
        # Teleport states q0 to q3 to Bob.
        # The resulting state q[i] might have a phase `pi`,
        # depending on outcome m[i].
        m = [None] * num_qubits
        for i in range(num_qubits):
            m[i] = teleport_state(epr_socket, theta[i])
        alice.flush()

        # Convert outcomes to integers to use them in calculations below.
        m = [int(m[i]) for i in range(num_qubits)]

        # Let Bob measure q1. We want to measure with angle phi1,
        # but send delta1 instead, which compensates for m1, r1 and theta1.
        delta1 = phi1 - theta[1] + r1 * np.pi - m[1] * np.pi
        send_meas_cmd(socket, delta1)
        s1 = recv_meas_outcome(socket)

        # Let Bob measure q2. We want to measure with angle phi2,
        # but send delta2 instead, which compensates for m1, s1, r1, and theta2.
        delta2 = phi2 - theta[2] + (s1 ^ r1) * np.pi + r2 * np.pi - m[2] * np.pi
        send_meas_cmd(socket, delta2)
        s2 = recv_meas_outcome(socket)

        # At this point, and before Bob measures both output qubits (q0 and q3)
        # in the Y basis, there are still some Pauli byproducts.
        # For q0, these byproducts are Z^m0 X^s1 X^r1.
        # For q3, these byproducts are Z^m3 X^s2 X^r2.
        # However, since these all commute with Y, we will simply let
        # Bob measure Y anyway, and apply bit-flips afterwards.
        result0 = recv_meas_outcome(socket)
        result1 = recv_meas_outcome(socket)

        # Flip bits according to Pauli byproducts (^ = xor).
        if (s1 ^ r1 ^ m[0]) == 1:
            result0 = 1 - result0
        if (s2 ^ r2 ^ m[3]) == 1:
            result1 = 1 - result1

        return {
            "result0": result0,
            "result1": result1,
            "phi1": phi1,
            "phi2": phi2,
            "delta1": delta1,
            "delta2": delta2,
            "s1": s1,
            "s2": s2,
            "m": m,
            "b0": b0,
            "b1": b1,
            "r1": r1,
            "r2": r2,
            "theta1": theta[1],
            "theta2": theta[2],
        }
