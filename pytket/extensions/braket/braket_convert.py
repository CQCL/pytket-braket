# Copyright Quantinuum
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

from numpy import pi

from braket.circuits import Circuit as BK_Circuit  # type: ignore
from pytket.circuit import Circuit, OpType, Qubit

if TYPE_CHECKING:
    from pytket.circuit import Node


def _normalize_angle(n: float) -> float:
    n0 = n % 4
    if n0 > 2:  # noqa: PLR2004
        n0 = n0 - 4
    return n0


def tk_to_braket(  # noqa: PLR0912, PLR0915
    tkcirc: Circuit,
    mapped_qubits: bool = False,
    forced_qubits: list[int] | None = None,
    force_ops_on_target_qubits: bool = False,
) -> tuple[BK_Circuit, list[int], dict[int, int]]:
    """
    Convert a tket :py:class:`~.pytket._tket.circuit.Circuit` to a braket circuit.

    :param tkcirc: circuit to be converted
    :param mapped_qubits: if True, `tkcirc` must have a single one-dimensional qubit
        register; the indices of the qubits in that register correspond directly to the
        qubit identifiers in the braket circuit
    :param forced_qubits: optional list of braket qubit identifiers to include in the
        converted circuit even if they are unused
    :param force_ops_on_target_qubits: if True, add no-ops to all target qubits
    :returns: circuit converted to braket; list of braket qubit ids corresponding in
        order of corresponding positions in tkcirc.qubits; (partial) map from braket
        qubit ids to corresponding pytket bit indices holding measurement results
    """
    tkcirc1 = tkcirc.copy()
    if tkcirc1.n_gates_of_type(OpType.Measure) == 0:
        tkcirc1.replace_implicit_wire_swaps()
    bkcirc = BK_Circuit()
    target_qubits = []
    for i, qb in enumerate(tkcirc1.qubits):
        bkq = qb.index[0] if mapped_qubits else i
        target_qubits.append(bkq)
    measures = {}
    # Add no-ops on all qubits to ensure that even unused qubits are included in bkcirc:
    if force_ops_on_target_qubits:
        bkcirc.i(target_qubits)
    if forced_qubits is not None:
        bkcirc.i(forced_qubits)
    # Add commands
    for cmd in tkcirc1.get_commands():
        qbs = [
            qb.index[0] if mapped_qubits else tkcirc1.qubits.index(qb)
            for qb in cmd.qubits
        ]
        cbs = [tkcirc1.bits.index(cb) for cb in cmd.bits]
        op = cmd.op
        optype = op.type
        if optype == OpType.Barrier:
            continue
        params = op.params
        if optype == OpType.CCX:
            bkcirc.ccnot(*qbs)
        elif optype == OpType.CX:
            bkcirc.cnot(*qbs)
        elif optype == OpType.CU1:
            bkcirc.cphaseshift(*qbs, params[0] * pi)
        elif optype == OpType.CSWAP:
            bkcirc.cswap(*qbs)
        elif optype == OpType.CY:
            bkcirc.cy(*qbs)
        elif optype == OpType.CZ:
            bkcirc.cz(*qbs)
        elif optype == OpType.H:
            bkcirc.h(*qbs)
        elif optype == OpType.noop:
            pass
        elif optype == OpType.ISWAPMax:
            bkcirc.iswap(*qbs)
        elif optype == OpType.U1:
            bkcirc.phaseshift(*qbs, params[0] * pi)
        # Rx is a gate in the gate set of Rigetti's Ankaa-3.
        # It seems that the verbatim execution accepts an angle in (2*pi, -2*pi).
        elif optype == OpType.Rx:
            bkcirc.rx(*qbs, _normalize_angle(params[0]) * pi)
        elif optype == OpType.Ry:
            bkcirc.ry(*qbs, params[0] * pi)
        # Rz is a gate in the gate set of Rigetti's Ankaa-3.
        # It seems that the verbatim execution accepts an angle in (2*pi, -2*pi).
        elif optype == OpType.Rz:
            bkcirc.rz(*qbs, _normalize_angle(params[0]) * pi)
        elif optype == OpType.S:
            bkcirc.s(*qbs)
        elif optype == OpType.Sdg:
            bkcirc.si(*qbs)
        elif optype == OpType.SWAP:
            bkcirc.swap(*qbs)
        elif optype == OpType.T:
            bkcirc.t(*qbs)
        elif optype == OpType.Tdg:
            bkcirc.ti(*qbs)
        # V amd Vdg differ by a pi/4 phase from braket according to the get_matrix
        # methods. However, braket circuits do not seem to be phase-aware.
        elif optype == OpType.V:
            bkcirc.v(*qbs)
        elif optype == OpType.Vdg:
            bkcirc.vi(*qbs)
        elif optype == OpType.X:
            bkcirc.x(*qbs)
        elif optype == OpType.XXPhase:
            bkcirc.xx(*qbs, params[0] * pi)
        elif optype == OpType.ISWAP:
            bkcirc.xy(*qbs, params[0] * pi)
        elif optype == OpType.Y:
            bkcirc.y(*qbs)
        elif optype == OpType.YYPhase:
            bkcirc.yy(*qbs, params[0] * pi)
        elif optype == OpType.Z:
            bkcirc.z(*qbs)
        elif optype == OpType.ZZPhase:
            bkcirc.zz(*qbs, _normalize_angle(params[0]) * pi)
        elif optype == OpType.GPI:
            bkcirc.gpi(*qbs, _normalize_angle(params[0]) * pi)
        elif optype == OpType.GPI2:
            bkcirc.gpi2(*qbs, _normalize_angle(params[0]) * pi)
        elif optype == OpType.AAMS:
            bkcirc.ms(
                *qbs,
                _normalize_angle(params[1]) * pi,
                _normalize_angle(params[2]) * pi,
                _normalize_angle(params[0]) * pi,
            )
        # PhasedX is a gate in the gate set of IQM's Garnet.
        # It seems that the verbatim execution accepts an angle in (2*pi, -2*pi).
        elif optype == OpType.PhasedX:
            bkcirc.prx(
                *qbs, _normalize_angle(params[0]) * pi, _normalize_angle(params[1]) * pi
            )
        elif optype == OpType.Measure:
            # Not wanted by braket, but must be tracked for final conversion of results.
            measures[qbs[0]] = cbs[0]
        else:
            raise NotImplementedError(f"Cannot convert {op.get_name()} to braket")
    return (bkcirc, target_qubits, measures)


def braket_to_tk(bkcirc: BK_Circuit) -> Circuit:  # noqa: PLR0912, PLR0915
    """
    Convert a braket circuit to a tket :py:class:`~.pytket._tket.circuit.Circuit`

    :param bkcirc: circuit to be converted

    :returns: circuit converted to tket
    """
    tkcirc = Circuit()
    for qb in bkcirc.qubits:
        tkcirc.add_qubit(Qubit("q", int(qb)))
    for instr in bkcirc.instructions:
        op = instr.operator
        qbs = [int(qb) for qb in instr.target]
        opname = op.name
        if opname == "CCNot":
            tkcirc.add_gate(OpType.CCX, qbs)
        elif opname == "CNot":
            tkcirc.add_gate(OpType.CX, qbs)
        elif opname == "CPhaseShift":
            tkcirc.add_gate(OpType.CU1, op.angle / pi, qbs)
        elif opname == "CSwap":
            tkcirc.add_gate(OpType.CSWAP, qbs)
        elif opname == "CY":
            tkcirc.add_gate(OpType.CY, qbs)
        elif opname == "CZ":
            tkcirc.add_gate(OpType.CZ, qbs)
        elif opname == "H":
            tkcirc.add_gate(OpType.H, qbs)
        elif opname == "I":
            pass
        elif opname == "ISwap":
            tkcirc.add_gate(OpType.ISWAPMax, qbs)
        elif opname == "PhaseShift":
            tkcirc.add_gate(OpType.U1, op.angle / pi, qbs)
        elif opname == "PRx":
            tkcirc.add_gate(OpType.PhasedX, [op.angle_1 / pi, op.angle_2 / pi], qbs)
        elif opname == "Rx":
            tkcirc.add_gate(OpType.Rx, op.angle / pi, qbs)
        elif opname == "Ry":
            tkcirc.add_gate(OpType.Ry, op.angle / pi, qbs)
        elif opname == "Rz":
            tkcirc.add_gate(OpType.Rz, op.angle / pi, qbs)
        elif opname == "S":
            tkcirc.add_gate(OpType.S, qbs)
        elif opname == "Si":
            tkcirc.add_gate(OpType.Sdg, qbs)
        elif opname == "Swap":
            tkcirc.add_gate(OpType.SWAP, qbs)
        elif opname == "T":
            tkcirc.add_gate(OpType.T, qbs)
        elif opname == "Ti":
            tkcirc.add_gate(OpType.Tdg, qbs)
        elif opname == "V":
            tkcirc.add_gate(OpType.V, qbs)
            tkcirc.add_phase(0.25)
        elif opname == "Vi":
            tkcirc.add_gate(OpType.Vdg, qbs)
            tkcirc.add_phase(-0.25)
        elif opname == "X":
            tkcirc.add_gate(OpType.X, qbs)
        elif opname == "XX":
            tkcirc.add_gate(OpType.XXPhase, op.angle / pi, qbs)
        elif opname == "XY":
            tkcirc.add_gate(OpType.ISWAP, op.angle / pi, qbs)
        elif opname == "Y":
            tkcirc.add_gate(OpType.Y, qbs)
        elif opname == "YY":
            tkcirc.add_gate(OpType.YYPhase, op.angle / pi, qbs)
        elif opname == "Z":
            tkcirc.add_gate(OpType.Z, qbs)
        elif opname == "ZZ":
            tkcirc.add_gate(OpType.ZZPhase, op.angle / pi, qbs)
        else:
            # The following don't have direct equivalents:
            # - CCPrx: classically controlled PhasedX.
            # - CPhaseShift00, CPhaseShift01, CPhaseShift10: diagonal unitaries with 1s
            # on the diagonal except for a phase e^{ia} in the (0,0), (1,1) or (2,2)
            # position respectively.
            # - MeasureFF: measurement with feedforward.
            # - PSwap: unitary with 1s at (0,0) and (3,3), a phase e^{ia} at (1,2) and
            # (2,1), and zeros elsewhere.
            # They could be decomposed into pytket gates, but it would be better to add
            # the gate types to tket.
            # The "Unitary" type could be represented as a box in the 1q and 2q cases,
            # but not in general.
            raise NotImplementedError(f"Cannot convert {opname} to tket")
    return tkcirc


def get_avg_characterisation(
    characterisation: dict[str, Any],
) -> dict[str, dict["Node", float]]:
    """
    Convert gate-specific characterisation into readout, one- and two-qubit errors

    Used to convert the stored full `characterisation` into an input
    noise characterisation for NoiseAwarePlacement
    """

    K = TypeVar("K")
    V1 = TypeVar("V1")
    V2 = TypeVar("V2")
    map_values_t = Callable[[Callable[[V1], V2], dict[K, V1]], dict[K, V2]]
    map_values: map_values_t = lambda f, d: {k: f(v) for k, v in d.items()}

    node_errors = cast(
        "dict[Node, dict[OpType, float]]", characterisation["NodeErrors"]
    )
    link_errors = cast(
        "dict[tuple[Node, Node], dict[OpType, float]]", characterisation["EdgeErrors"]
    )
    readout_errors = cast(
        "dict[Node, list[list[float]]]", characterisation["ReadoutErrors"]
    )

    avg: Callable[[dict[Any, float]], float] = lambda xs: sum(xs.values()) / len(xs)
    avg_mat: Callable[[list[list[float]]], float] = (
        lambda xs: (xs[0][1] + xs[1][0]) / 2.0
    )
    avg_readout_errors = map_values(avg_mat, readout_errors)
    avg_node_errors = map_values(avg, node_errors)
    avg_link_errors = map_values(avg, link_errors)

    return {
        "node_errors": avg_node_errors,
        "link_errors": avg_link_errors,
        "readout_errors": avg_readout_errors,
    }
