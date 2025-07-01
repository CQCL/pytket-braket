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

import json
import os
from collections import Counter
from typing import cast

import numpy as np
import pytest
from hypothesis import given, settings, strategies

from pytket.architecture import FullyConnected
from pytket.circuit import Bit, Circuit, OpType, Qubit
from pytket.extensions.braket import BraketBackend
from pytket.passes import BasePass, SequencePass
from pytket.pauli import Pauli, QubitPauliString
from pytket.utils.expectations import (
    get_operator_expectation_value,
    get_pauli_expectation_value,
)
from pytket.utils.operators import QubitPauliOperator

# To test on AWS backends, first set up auth using boto3, then set the S3 bucket and
# folder in pytket config. See:
# https://github.com/aws/amazon-braket-sdk-python
# Otherwise, all tests are run on a local simulator.
skip_remote_tests: bool = os.getenv("PYTKET_RUN_REMOTE_TESTS") is None
REASON = "PYTKET_RUN_REMOTE_TESTS not set (requires configuration of AWS storage)"


def skip_if_device_is_not_available(backend: BraketBackend) -> None:
    """Skip the test if the device of the provided `backend` is not available"""
    if not backend._device.is_available:  # noqa: SLF001
        pytest.skip(f"{backend._device.arn} is not available")  # noqa: SLF001


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [{"device_type": "quantum-simulator", "provider": "amazon", "device": "sv1"}],
    indirect=True,
)
def test_simulator(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.supports_shots
    c = Circuit(2).H(0).CX(0, 1)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    n_shots = 100
    h0, h1 = b.process_circuits([c, c], n_shots)
    res0 = b.get_result(h0)
    readouts = res0.get_shots()
    assert all(readouts[i][0] == readouts[i][1] for i in range(n_shots))
    res1 = b.get_result(h1)
    counts = res1.get_counts()
    assert len(counts) <= 2
    assert sum(counts.values()) == n_shots
    zi = QubitPauliString(Qubit(0), Pauli.Z)
    assert b.get_pauli_expectation_value(
        c, zi, poll_timeout_seconds=60, poll_interval_seconds=1
    ) == pytest.approx(0)

    # Circuit with unused qubits
    c = Circuit(3).H(1).CX(1, 2)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 1)
    res = b.get_result(h)
    readout = res.get_shots()[0]
    assert readout[1] == readout[2]


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [{"device_type": "quantum-simulator", "provider": "amazon", "device": "dm1"}],
    indirect=True,
)
def test_dm_simulator(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.supports_density_matrix
    c = Circuit(2).H(0).SWAP(0, 1)
    cc = b.get_compiled_circuit(c)
    h = b.process_circuit(cc)
    r = b.get_result(h)
    m = r.get_density_matrix()
    m0 = np.zeros((4, 4), dtype=complex)
    m0[0, 0] = m0[1, 0] = m0[0, 1] = m0[1, 1] = 0.5
    assert np.allclose(m, m0)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [{"device_type": "quantum-simulator", "provider": "amazon", "device": "tn1"}],
    indirect=True,
)
def test_tn1_simulator(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.supports_shots
    c = Circuit(2).H(0).CX(0, 1)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    n_shots = 100
    h0, h1 = b.process_circuits([c, c], n_shots)
    res0 = b.get_result(h0, timeout=200)
    readouts = res0.get_shots()
    assert all(readouts[i][0] == readouts[i][1] for i in range(n_shots))
    res1 = b.get_result(h1, timeout=200)
    counts = res1.get_counts()
    assert len(counts) <= 2
    assert sum(counts.values()) == n_shots
    # Circuit with unused qubits
    c = Circuit(3).H(1).CX(1, 2)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 1)
    res = b.get_result(h, timeout=200)
    readout = res.get_shots()[0]
    assert readout[1] == readout[2]


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Aria-1",
        },
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Aria-2",
        },
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Forte-1",
        },
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Forte-Enterprise-1",
        },
    ],
    indirect=True,
)
def test_ionq(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.persistent_handles
    assert b.supports_shots
    assert not b.supports_state
    assert not b.verbatim
    # If b._supports_client_qubit_mapping is False, the qubit labels in a circuit
    # are modified by Braket when executing a job.
    assert b._supports_client_qubit_mapping  # noqa: SLF001

    # Device is fully connected
    arch = b.backend_info.architecture
    assert isinstance(arch, FullyConnected)

    chars = b.characterisation
    assert chars is not None
    assert chars is not None
    assert all(s in chars for s in ["NodeErrors", "EdgeErrors", "ReadoutErrors"])
    assert b._characteristics is not None  # noqa: SLF001
    fid = b._characteristics["fidelity"]  # noqa: SLF001
    assert "1Q" in fid
    assert "2Q" in fid
    assert "spam" in fid
    tim = b._characteristics["timing"]  # noqa: SLF001
    assert "T1" in tim
    assert "T2" in tim

    c = (
        Circuit(3)
        .add_gate(OpType.XXPhase, 0.15, [0, 1])
        .add_gate(OpType.YYPhase, 0.15, [1, 2])
        .add_gate(OpType.SWAP, [0, 2])
        .add_gate(OpType.CCX, [0, 1, 2])
    )
    assert not b.valid_circuit(c)
    c0 = b.get_compiled_circuit(c, optimisation_level=0)
    assert b.valid_circuit(c0)
    c1 = b.get_compiled_circuit(c, optimisation_level=1)
    assert b.valid_circuit(c1)
    c2 = b.get_compiled_circuit(c, optimisation_level=2)
    assert b.valid_circuit(c2)
    h = b.process_circuit(c0, 10)
    _ = b.circuit_status(h)
    b.cancel(h)

    # Circuit with unused qubits
    c = Circuit(11).H(9).CX(9, 10)
    c = b.get_compiled_circuit(c)
    with pytest.raises(Exception) as e:
        h = b.process_circuit(c, 1)
        assert "non-contiguous qubits" in str(e.value)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "rigetti",
            "device": "Ankaa-3",
            "region": "us-west-1",
        }
    ],
    indirect=True,
)
def test_rigetti(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.persistent_handles
    assert b.supports_shots
    assert not b.supports_state
    assert not b.verbatim
    # If b._supports_client_qubit_mapping is False, the qubit labels in a circuit
    # are modified by Braket when executing a job.
    assert b._supports_client_qubit_mapping  # noqa: SLF001

    chars = b.characterisation
    assert chars is not None
    assert all(s in chars for s in ["NodeErrors", "EdgeErrors", "ReadoutErrors"])

    c = (
        Circuit(3)
        .add_gate(OpType.CCX, [0, 1, 2])
        .add_gate(OpType.U1, 0.15, [1])
        .add_gate(OpType.ISWAP, 0.15, [0, 2])
        .add_gate(OpType.XXPhase, 0.15, [1, 2])
    )
    assert not b.valid_circuit(c)
    c0 = b.get_compiled_circuit(c, optimisation_level=0)
    assert b.valid_circuit(c0)
    c1 = b.get_compiled_circuit(c, optimisation_level=1)
    assert b.valid_circuit(c1)
    c2 = b.get_compiled_circuit(c, optimisation_level=2)
    assert b.valid_circuit(c2)
    h = b.process_circuit(c0, 10)  # min shots = 10 for Rigetti
    _ = b.circuit_status(h)
    b.cancel(h)

    # Circuit with unused qubits
    c = Circuit(11).H(9).CX(9, 10)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 10)
    b.cancel(h)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "rigetti",
            "device": "Ankaa-3",
            "region": "us-west-1",
            "verbatim": True,
        }
    ],
    indirect=True,
)
def test_rigetti_verbatim(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.persistent_handles
    assert b.supports_shots
    assert not b.supports_state
    assert b.verbatim
    # If b._supports_client_qubit_mapping is False, the qubit labels in a circuit
    # are modified by Braket when executing a job. Verbatim execution requires
    # that b._supports_client_qubit_mapping is set to True.
    assert b._supports_client_qubit_mapping  # noqa: SLF001

    chars = b.characterisation
    assert chars is not None
    assert all(s in chars for s in ["NodeErrors", "EdgeErrors", "ReadoutErrors"])

    c = (
        Circuit(3)
        .add_gate(OpType.CCX, [0, 1, 2])
        .add_gate(OpType.U1, 0.15, [1])
        .add_gate(OpType.ISWAP, 0.15, [0, 2])
        .add_gate(OpType.XXPhase, 0.15, [1, 2])
        .measure_all()
    )
    assert not b.valid_circuit(c)
    for opt_level in range(3):
        c = b.get_compiled_circuit(c, optimisation_level=opt_level)
        assert b.valid_circuit(c)
        # Valid angles for Rx are integer multiples of pi/2
        for i in c:
            if i.op.type == OpType.Rx:
                assert i.op.params[0] % 0.5 == 0
    h = b.process_circuit(c, 10)  # min shots = 10 for Rigetti
    _ = b.circuit_status(h)
    b.cancel(h)

    # Circuit with unused qubits
    c = Circuit(11).H(9).CX(9, 10)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 10)
    b.cancel(h)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "rigetti",
            "device": "Ankaa-3",
            "region": "us-west-1",
        }
    ],
    indirect=True,
)
def test_rigetti_with_rerouting(authenticated_braket_backend: BraketBackend) -> None:
    # A circuit that requires rerouting to a non-fully-connected architecture
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    c = Circuit(4).CX(0, 1).CX(0, 2).CX(0, 3).CX(1, 2).CX(1, 3).CX(2, 3)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 10)
    b.cancel(h)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "iqm",
            "device": "Garnet",
            "region": "eu-north-1",
        }
    ],
    indirect=True,
)
def test_iqm(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.persistent_handles
    assert b.supports_shots
    assert not b.supports_state
    assert not b.verbatim
    # If b._supports_client_qubit_mapping is False, the qubit labels in a circuit
    # are modified by Braket when executing a job.
    assert b._supports_client_qubit_mapping  # noqa: SLF001

    chars = b.characterisation
    assert chars is not None
    assert all(s in chars for s in ["NodeErrors", "EdgeErrors", "ReadoutErrors"])

    c = (
        Circuit(3)
        .add_gate(OpType.CCX, [0, 1, 2])
        .add_gate(OpType.U1, 0.15, [1])
        .add_gate(OpType.ISWAP, 0.15, [0, 2])
        .add_gate(OpType.XXPhase, 0.15, [1, 2])
    )
    assert not b.valid_circuit(c)
    c0 = b.get_compiled_circuit(c, optimisation_level=0)
    assert b.valid_circuit(c0)
    c1 = b.get_compiled_circuit(c, optimisation_level=1)
    assert b.valid_circuit(c1)
    c2 = b.get_compiled_circuit(c, optimisation_level=2)
    assert b.valid_circuit(c2)
    h = b.process_circuit(c0, 10)
    _ = b.circuit_status(h)
    b.cancel(h)

    # Circuit with unused qubits
    c = Circuit(20).H(5).CX(5, 6)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 10)
    b.cancel(h)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "iqm",
            "device": "Garnet",
            "region": "eu-north-1",
            "verbatim": True,
        }
    ],
    indirect=True,
)
def test_iqm_verbatim(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.persistent_handles
    assert b.supports_shots
    assert not b.supports_state
    assert b.verbatim
    # If b._supports_client_qubit_mapping is False, the qubit labels in a circuit
    # are modified by Braket when executing a job. Verbatim execution requires
    # that b._supports_client_qubit_mapping is set to True.
    assert b._supports_client_qubit_mapping  # noqa: SLF001

    chars = b.characterisation
    assert chars is not None
    assert all(s in chars for s in ["NodeErrors", "EdgeErrors", "ReadoutErrors"])

    c = (
        Circuit(3)
        .add_gate(OpType.CCX, [0, 1, 2])
        .add_gate(OpType.U1, 0.15, [1])
        .add_gate(OpType.ISWAP, 0.15, [0, 2])
        .add_gate(OpType.XXPhase, 0.15, [1, 2])
        .measure_all()
    )
    assert not b.valid_circuit(c)
    c0 = b.get_compiled_circuit(c, optimisation_level=0)
    assert b.valid_circuit(c0)
    c1 = b.get_compiled_circuit(c, optimisation_level=1)
    assert b.valid_circuit(c1)
    c2 = b.get_compiled_circuit(c, optimisation_level=2)
    assert b.valid_circuit(c2)
    h = b.process_circuit(c0, 10)
    _ = b.circuit_status(h)
    b.cancel(h)

    # Circuit with unused qubits
    c = Circuit(20).H(5).CX(5, 6)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, 10)
    b.cancel(h)


def test_local_simulator() -> None:
    b = BraketBackend(local=True)
    assert b.supports_shots
    assert b.supports_counts
    c = Circuit(2).H(0).CX(0, 1)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    n_shots = 100
    h = b.process_circuit(c, n_shots)
    res = b.get_result(h)
    readouts = res.get_shots()
    assert all(readouts[i][0] == readouts[i][1] for i in range(n_shots))
    counts = res.get_counts()
    assert len(counts) <= 2
    assert sum(counts.values()) == n_shots


def test_implicit_qubit_perm() -> None:
    # https://github.com/CQCL/pytket-braket/issues/55
    b = BraketBackend(local=True)

    # State, without measurement:
    c0 = Circuit(3).X(0).X(2).SWAP(0, 1)
    c1 = b.get_compiled_circuit(c0)
    s0 = b.run_circuit(c0).get_state()
    s1 = b.run_circuit(c1).get_state()
    assert np.isclose(abs(s0[3]), 1.0)
    assert np.isclose(abs(s1[3]), 1.0)

    # Counts, with measurement:
    c0.measure_all()
    c1 = b.get_compiled_circuit(c0)
    x0 = b.run_circuit(c0, n_shots=2).get_counts()
    x1 = b.run_circuit(c1, n_shots=2).get_counts()
    assert x0 == Counter({(0, 1, 1): 2})
    assert x1 == Counter({(0, 1, 1): 2})


def test_local_dm_simulator() -> None:
    b = BraketBackend(local=True, local_device="braket_dm")
    assert b.supports_shots
    assert b.supports_counts
    assert b.supports_density_matrix
    c = Circuit(2).H(0).CX(0, 1)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c)
    res = b.get_result(h)
    dm = res.get_density_matrix()
    dm0 = np.zeros((4, 4), dtype=complex)
    dm0[0, 0] = dm0[0, 3] = dm0[3, 0] = dm0[3, 3] = 0.5
    assert np.allclose(dm, dm0)


def test_expectation() -> None:
    b = BraketBackend(local=True)
    assert b.supports_expectation
    c = Circuit(2, 2)
    c.Rz(0.5, 0)
    zi = QubitPauliString(Qubit(0), Pauli.Z)
    iz = QubitPauliString(Qubit(1), Pauli.Z)
    op = QubitPauliOperator({zi: 0.3, iz: -0.1})
    assert get_pauli_expectation_value(c, zi, b) == pytest.approx(1.0)
    assert get_operator_expectation_value(c, op, b) == pytest.approx(0.2)
    c.X(0)
    assert get_pauli_expectation_value(c, zi, b) == pytest.approx(-1.0)
    assert get_operator_expectation_value(c, op, b) == pytest.approx(-0.4)


def test_variance() -> None:
    b = BraketBackend(local=True)
    assert b.supports_variance
    # - Prepare a state (1/sqrt(2), 1/sqrt(2)).
    # - Measure w.r.t. the operator Z which has evcs (1,0) (evl=+1) and (0,1) (evl=-1).
    # - Get +1 with prob. 1/2 and -1 with prob. 1/2.
    c = Circuit(1).H(0)
    z = QubitPauliString(Qubit(0), Pauli.Z)
    assert b.get_pauli_expectation_value(c, z) == pytest.approx(0)
    assert b.get_pauli_variance(c, z) == pytest.approx(1)
    op = QubitPauliOperator({z: 3})
    assert b.get_operator_expectation_value(c, op) == pytest.approx(0)
    assert b.get_operator_variance(c, op) == pytest.approx(9)


def test_moments_with_shots() -> None:
    b = BraketBackend(local=True)
    c = Circuit(1).H(0)
    z = QubitPauliString(Qubit(0), Pauli.Z)
    e = b.get_pauli_expectation_value(c, z, n_shots=10)
    assert abs(e) <= 1
    v = b.get_pauli_variance(c, z, n_shots=10)
    assert v <= 1
    op = QubitPauliOperator({z: 3})
    e = b.get_operator_expectation_value(c, op, n_shots=10)
    assert abs(e) <= 3
    v = b.get_operator_variance(c, op, n_shots=10)
    assert v <= 9


def test_probabilities() -> None:
    b = BraketBackend(local=True)
    c = (
        Circuit(2)
        .H(0)
        .Rx(0.8, 1)
        .Rz(0.5, 0)
        .CX(0, 1)
        .Ry(0.3, 1)
        .CX(1, 0)
        .T(0)
        .S(1)
        .CX(0, 1)
        .Ry(1.8, 0)
    )
    probs01 = b.get_probabilities(c)
    probs10 = b.get_probabilities(c, qubits=[1, 0])
    probs0 = b.get_probabilities(c, qubits=[0])
    probs1 = b.get_probabilities(c, qubits=[1])
    assert probs01[0] == pytest.approx(probs10[0])
    assert probs01[1] == pytest.approx(probs10[2])
    assert probs01[2] == pytest.approx(probs10[1])
    assert probs01[3] == pytest.approx(probs10[3])
    assert probs0[0] == pytest.approx(probs01[0] + probs01[1])
    assert probs1[0] == pytest.approx(probs01[0] + probs01[2])
    h = b.process_circuit(c)
    res = b.get_result(h)
    dist = res.get_distribution()
    for (a0, a1), p in dist.items():
        assert probs01[2 * a0 + a1] == pytest.approx(p)


def test_probabilities_with_shots() -> None:
    b = BraketBackend(local=True)
    c = Circuit(2).V(1).CX(1, 0).S(1)
    c.measure_all()
    probs_all = b.get_probabilities(c, n_shots=10)
    assert len(probs_all) == 4
    assert sum(probs_all) == pytest.approx(1)
    assert probs_all[1] == 0
    assert probs_all[2] == 0
    probs1 = b.get_probabilities(c, n_shots=10, qubits=[1])
    assert len(probs1) == 2
    assert sum(probs1) == pytest.approx(1)
    h = b.process_circuit(c, n_shots=10)
    res = b.get_result(h)
    dist = res.get_distribution()
    assert (1, 0) not in dist
    assert (0, 1) not in dist


def test_amplitudes() -> None:
    b = BraketBackend(local=True)
    c = Circuit(2).V(0).V(1).CX(1, 0).S(1)
    amps = b.get_amplitudes(c, states=["00", "01", "10", "11"])
    assert amps["00"] == pytest.approx(amps["11"])
    assert amps["01"] == pytest.approx(amps["10"])


def test_state() -> None:
    b = BraketBackend(local=True)
    c = Circuit(3).V(0).V(1).CX(1, 0).S(1).CCX(0, 1, 2)
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c)
    res = b.get_result(h)
    v = res.get_state()
    assert np.vdot(v, v) == pytest.approx(1)


def test_default_pass() -> None:
    b = BraketBackend(local=True)
    for ol in range(3):
        comp_pass = b.default_compilation_pass(ol)
        c = Circuit(3, 3)
        c.H(0)
        c.CX(0, 1)
        c.CSWAP(1, 0, 2)
        c.ZZPhase(0.84, 2, 0)
        comp_pass.apply(c)
        for pred in b.required_predicates:
            assert pred.verify(c)


@given(
    n_shots=strategies.integers(min_value=1, max_value=10),
    n_bits=strategies.integers(min_value=0, max_value=10),
)
@settings(deadline=None)
def test_shots_bits_edgecases(n_shots: int, n_bits: int) -> None:
    braket_backend = BraketBackend(local=True)
    c = Circuit(n_bits, n_bits)
    c.measure_all()

    # TODO TKET-813 add more shot based backends and move to integration tests
    h = braket_backend.process_circuit(c, n_shots)
    res = braket_backend.get_result(h)

    correct_shots = np.zeros((n_shots, n_bits), dtype=int)
    correct_shape = (n_shots, n_bits)
    correct_counts = Counter({(0,) * n_bits: n_shots})
    # BackendResult/
    assert np.array_equal(res.get_shots(), correct_shots)
    assert res.get_shots().shape == correct_shape
    assert res.get_counts() == correct_counts

    # Direct
    res = braket_backend.run_circuit(c, n_shots=n_shots)
    assert np.array_equal(res.get_shots(), correct_shots)
    assert res.get_shots().shape == correct_shape
    assert res.get_counts() == correct_counts


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Aria-1",
        }
    ],
    indirect=True,
)
def test_postprocess_ionq(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    assert b.supports_contextual_optimisation
    c = Circuit(2).H(0).CX(0, 1).Y(0)
    c.measure_all()
    c = b.get_compiled_circuit(c)
    h = b.process_circuit(c, n_shots=10, postprocess=True)
    ppcirc = Circuit.from_dict(json.loads(cast("str", h[5])))
    ppcmds = ppcirc.get_commands()
    assert len(ppcmds) > 0
    assert all(ppcmd.op.type == OpType.ClassicalTransform for ppcmd in ppcmds)
    b.cancel(h)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize("authenticated_braket_backend", [None], indirect=True)
def test_retrieve_available_devices(
    authenticated_braket_backend: BraketBackend,
) -> None:
    backend_infos = authenticated_braket_backend.available_devices(
        aws_session=authenticated_braket_backend._aws_session  # noqa: SLF001
    )
    assert len(backend_infos) > 0
    # Test annealers are filtered out.
    backend_infos = authenticated_braket_backend.available_devices(
        region="us-west-2",
        aws_session=authenticated_braket_backend._aws_session,  # noqa: SLF001
    )
    assert len(backend_infos) > 0


def test_partial_measurement() -> None:
    b = BraketBackend(local=True)
    c = Circuit(4, 4)
    c.H(0).CX(0, 1)
    c.Measure(0, 1)
    c.Measure(2, 0)
    c = b.get_compiled_circuit(c)
    n_shots = 100
    h = b.process_circuit(c, n_shots)
    res = b.get_result(h)
    readouts = res.get_shots()
    assert all(len(readouts[i]) == 2 for i in range(n_shots))
    assert all(readouts[i][0] == 0 for i in range(n_shots))
    counts = res.get_counts()
    assert sum(counts.values()) == n_shots


def test_multiple_indices() -> None:
    b = BraketBackend(local=True)
    c = Circuit(0, 2)
    q0 = Qubit("Z", [0, 0])
    q1 = Qubit("Z", [0, 1])
    c.add_qubit(q0)
    c.add_qubit(q1)
    c.H(q0)
    c.CX(q0, q1)
    c.Measure(q0, Bit(0))
    c.Measure(q1, Bit(1))
    c1 = b.get_compiled_circuit(c)
    h = b.process_circuit(c1, 100)
    res = b.get_result(h)
    readouts = res.get_shots()
    assert all(readout[0] == readout[1] for readout in readouts)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "provider": "rigetti",
            "device": "Ankaa-3",
            "region": "us-west-1",
        }
    ],
    indirect=True,
)
def test_multiple_indices_rigetti(authenticated_braket_backend: BraketBackend) -> None:
    b = authenticated_braket_backend
    skip_if_device_is_not_available(b)
    c = Circuit(0, 2)
    q0 = Qubit("Z", [0, 0])
    q1 = Qubit("Z", [0, 1])
    c.add_qubit(q0)
    c.add_qubit(q1)
    c.H(q0)
    c.CX(q0, q1)
    c.Measure(q0, Bit(0))
    c.Measure(q1, Bit(1))
    c1 = b.get_compiled_circuit(c)
    h = b.process_circuit(c1, 100)
    b.cancel(h)


# Helper function used for testing serialization
# Both local and remote backends are tested.
def run_serialization_test(backend: BraketBackend) -> None:
    for opt_level in range(3):
        default_pass = backend.default_compilation_pass(opt_level)
        original_pass_dict = default_pass.to_dict()
        reconstructed_pass = BasePass.from_dict(original_pass_dict)
        assert isinstance(reconstructed_pass, SequencePass)
        assert original_pass_dict == reconstructed_pass.to_dict()


def test_local_backend_pass_serialization() -> None:
    local_backend = BraketBackend(local=True)
    run_serialization_test(local_backend)


@pytest.mark.skipif(skip_remote_tests, reason=REASON)
@pytest.mark.parametrize(
    "authenticated_braket_backend",
    [
        {
            "device_type": "qpu",
            "region": "us-east-1",
            "provider": "ionq",
            "device": "Aria-1",
        },
        {
            "device_type": "qpu",
            "provider": "rigetti",
            "device": "Ankaa-3",
            "region": "us-west-1",
        },
        {
            "device_type": "qpu",
            "provider": "iqm",
            "device": "Garnet",
            "region": "eu-north-1",
        },
    ],
    indirect=True,
)
def test_remote_backend_pass_serialization(
    authenticated_braket_backend: BraketBackend,
) -> None:
    run_serialization_test(authenticated_braket_backend)
