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
import time
import warnings
from collections.abc import Callable, Iterable, Sequence
from enum import Enum
from itertools import permutations
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)
from uuid import uuid4

import boto3
import numpy as np

import braket  # type: ignore
import braket.circuits  # type: ignore
from braket.aws import AwsDevice, AwsSession  # type: ignore
from braket.aws.aws_device import AwsDeviceType  # type: ignore
from braket.aws.aws_quantum_task import AwsQuantumTask  # type: ignore
from braket.circuits.observable import Observable  # type: ignore
from braket.circuits.qubit_set import QubitSet  # type: ignore
from braket.circuits.result_type import ResultType  # type: ignore
from braket.device_schema import DeviceActionType  # type: ignore
from braket.devices import LocalSimulator  # type: ignore
from braket.tasks.local_quantum_task import LocalQuantumTask  # type: ignore
from pytket.architecture import Architecture, FullyConnected
from pytket.backends import Backend, CircuitStatus, ResultHandle, StatusEnum
from pytket.backends.backend import KwargTypes
from pytket.backends.backend_exceptions import CircuitNotRunError
from pytket.backends.backendinfo import BackendInfo
from pytket.backends.backendresult import BackendResult
from pytket.backends.resulthandle import _ResultIdTuple
from pytket.circuit import Circuit, OpType
from pytket.extensions.braket._metadata import __extension_version__
from pytket.extensions.braket.braket_convert import (
    get_avg_characterisation,
    tk_to_braket,
)
from pytket.passes import (
    AutoRebase,
    AutoSquash,
    BasePass,
    CliffordSimp,
    CXMappingPass,
    DecomposeBoxes,
    FlattenRegisters,
    FullPeepholeOptimise,
    KAKDecomposition,
    NaivePlacementPass,
    RemoveRedundancies,
    RxFromSX,
    SequencePass,
    SimplifyInitial,
    SynthesiseTket,
)
from pytket.pauli import Pauli, QubitPauliString
from pytket.placement import NoiseAwarePlacement
from pytket.predicates import (
    ConnectivityPredicate,
    GateSetPredicate,
    MaxNQubitsPredicate,
    NoClassicalControlPredicate,
    NoFastFeedforwardPredicate,
    NoMidMeasurePredicate,
    NoSymbolsPredicate,
    Predicate,
)
from pytket.utils import prepare_circuit
from pytket.utils.operators import QubitPauliOperator
from pytket.utils.outcomearray import OutcomeArray

from .config import BraketConfig

if TYPE_CHECKING:
    from pytket.circuit import Node

# Known schemas for noise characteristics
IONQ_SCHEMA = {
    "name": "braket.device_schema.ionq.ionq_provider_properties",
    "version": "1",
}
RIGETTI_SCHEMA = {
    "name": "braket.device_schema.rigetti.rigetti_provider_properties",
    "version": "2",
}
IQM_SCHEMA = {
    "name": "braket.device_schema.iqm.iqm_provider_properties",
    "version": "1",
}

_gate_types = {
    "amplitude_damping": None,
    "bit_flip": None,
    "ccnot": OpType.CCX,
    "cc_prx": None,
    "cnot": OpType.CX,
    "cphaseshift": OpType.CU1,
    "cphaseshift00": None,
    "cphaseshift01": None,
    "cphaseshift10": None,
    "cswap": OpType.CSWAP,
    "cv": OpType.CV,
    "cy": OpType.CY,
    "cz": OpType.CZ,
    "depolarizing": None,
    "ecr": OpType.ECR,
    "end_verbatim_box": None,
    "generalized_amplitude_damping": None,
    "h": OpType.H,
    "i": OpType.noop,
    "iswap": OpType.ISWAPMax,
    "kraus": None,
    "measure_ff": None,
    "pauli_channel": None,
    "pswap": None,
    "phase_damping": None,
    "phase_flip": None,
    "phaseshift": OpType.U1,
    "prx": OpType.PhasedX,
    "rx": OpType.Rx,
    "ry": OpType.Ry,
    "rz": OpType.Rz,
    "s": OpType.S,
    "si": OpType.Sdg,
    "start_verbatim_box": None,
    "swap": OpType.SWAP,
    "t": OpType.T,
    "ti": OpType.Tdg,
    "two_qubit_dephasing": None,
    "two_qubit_depolarizing": None,
    "two_qubit_pauli_channel": None,
    "unitary": None,
    "v": OpType.V,
    "vi": OpType.Vdg,
    "x": OpType.X,
    "xx": OpType.XXPhase,
    "xy": OpType.ISWAP,
    "y": OpType.Y,
    "yy": OpType.YYPhase,
    "z": OpType.Z,
    "zz": OpType.ZZPhase,
    "gpi": OpType.GPI,
    "gpi2": OpType.GPI2,
    "ms": OpType.AAMS,
}

_multiq_gate_types = {
    "ccnot",
    "cnot",
    "cphaseshift",
    "cphaseshift00",
    "cphaseshift01",
    "cphaseshift10",
    "cswap",
    "cv",
    "cy",
    "cz",
    "ecr",
    "iswap",
    "pswap",
    "swap",
    "two_qubit_dephasing",
    "two_qubit_depolarizing",
    "unitary",
    "xx",
    "xy",
    "yy",
    "zz",
    "ms",
}

_observables = {
    Pauli.I: Observable.I(),
    Pauli.X: Observable.X(),
    Pauli.Y: Observable.Y(),
    Pauli.Z: Observable.Z(),
}


def _obs_from_qps(
    circuit: Circuit, pauli: QubitPauliString
) -> tuple[Observable, QubitSet]:
    obs, qbs = [], []
    for q, p in pauli.map.items():
        obs.append(_observables[p])
        qbs.append(circuit.qubits.index(q))
    return Observable.TensorProduct(obs), qbs


def _obs_from_qpo(operator: QubitPauliOperator, n_qubits: int) -> Observable:
    H = operator.to_sparse_matrix(n_qubits).toarray()
    return Observable.Hermitian(H)


def _get_result(  # noqa: PLR0913
    completed_task: AwsQuantumTask | LocalQuantumTask,
    target_qubits: list[int],
    measures: dict[int, int],
    want_state: bool,
    want_dm: bool,
    ppcirc: Circuit | None = None,
) -> dict[str, BackendResult]:
    """Get a result from a completed task.

    :param completed_task: braket task
    :param target_qubits: list of braket qubit ids
    :param measures: map from measured braket qubit ids to original circuit bit indices
    :param want_state: whether we want a statevector result
    :paran want_dm: whether we want a density-matrix result
    :param ppcirc: classical postprocessing circuit, if any
    """
    result = completed_task.result()
    kwargs = {}
    if want_state or want_dm:
        assert ppcirc is None
        if want_state:
            kwargs["state"] = result.get_value_by_result_type(ResultType.StateVector())
        if want_dm:
            m = result.get_value_by_result_type(
                ResultType.DensityMatrix(target=target_qubits)
            )
            if type(completed_task) == AwsQuantumTask:  # noqa: E721
                kwargs["density_matrix"] = np.array(
                    [[complex(x, y) for x, y in row] for row in m], dtype=complex
                )
            else:
                kwargs["density_matrix"] = m
    else:
        qubit_index = [0] * len(measures)
        for q, b in measures.items():
            qubit_index[b] = result.measured_qubits.index(q)
        measurements = result.measurements[:, qubit_index]
        kwargs["shots"] = OutcomeArray.from_readouts(measurements)
        kwargs["ppcirc"] = ppcirc
    return {"result": BackendResult(**kwargs)}


class _DeviceType(str, Enum):
    LOCAL = "LOCAL"
    SIMULATOR = "SIMULATOR"
    QPU = "QPU"


class BraketBackend(Backend):
    """Interface to Amazon Braket service"""

    _persistent_handles = True

    def __init__(  # noqa: PLR0912, PLR0913, PLR0915
        self,
        local: bool = False,
        local_device: str = "default",
        device: str | None = None,
        region: str = "",
        s3_bucket: str | None = None,
        s3_folder: str | None = None,
        device_type: str | None = None,
        provider: str | None = None,
        aws_session: AwsSession | None = None,
        verbatim: bool = False,
    ):
        """
        Construct a new braket backend.

        If `local=True`, other parameters are ignored.

        All parameters except `device` can be set in config using
        :py:meth:`pytket.extensions.braket.backends.config.set_braket_config`.
        For `device_type`, `provider` and `device` if no parameter
        is specified as a keyword argument or
        in the config file the defaults specified below are used.

        :param local: use simulator running on local machine,
            default: False
        :param local_device: name of local device (ignored if local=False) -- e.g.
            "braket_sv" (default) or "braket_dm".
        :param device: device name from device ARN (e.g. "ionQdevice", "Aspen-8", ...),
            default: "sv1"
        :param region: region from device ARN, default: ""
        :param s3_bucket: name of S3 bucket to store results
        :param s3_folder: name of folder ("key") in S3 bucket to store results in
        :param device_type: device type from device ARN (e.g. "qpu"),
            default: "quantum-simulator"
        :param provider: provider name from device ARN (e.g. "ionq", "rigetti", ...),
            default: "amazon"
        :param aws_session: braket AwsSession object, to pass credentials in if not
            configured on local machine
        :param verbatim: use the feature "verbatim-compilation".
            If verbatim-compilation = True, you can execute your circuits composed of
            the primitive gates supported by QPU without any modifications.
            For more details, see https://docs.aws.amazon.com/braket/latest/developerguide/braket-constructing-circuit.html#verbatim-compilation
            default: False
        """
        super().__init__()
        # load config
        config = BraketConfig.from_default_config_file()
        if s3_bucket is None:
            s3_bucket = config.s3_bucket
        if s3_folder is None:
            s3_folder = config.s3_folder
        if device_type is None:
            device_type = config.device_type
        if provider is None:
            provider = config.provider

        # set defaults if not overridden
        if device_type is None:
            device_type = "quantum-simulator"
        if provider is None:
            provider = "amazon"
        if device is None:
            device = "sv1"

        # set up AwsSession to use; if it's None, braket will create sessions as needed
        self._aws_session = aws_session

        self._verbatim = verbatim

        if local:
            self._device = LocalSimulator(backend=local_device)
            self._device_type = _DeviceType.LOCAL
        else:
            self._device = AwsDevice(
                "arn:aws:braket:"
                + region
                + "::"
                + "/".join(  # noqa: FLY002
                    ["device", device_type, provider, device],
                ),
                aws_session=self._aws_session,
            )
            # self._s3_dest must be of type Optional[Tuple[str, str]]
            if s3_bucket is None or s3_folder is None:
                self._s3_dest = None
                if s3_bucket is None and s3_folder is not None:
                    warnings.warn(  # noqa: B028
                        "'s3_bucket' is missing, use the default s3 destination."
                    )
                elif s3_bucket is not None and s3_folder is None:
                    warnings.warn(  # noqa: B028
                        "'s3_folder' is missing, use the default s3 destination."
                    )
            else:
                self._s3_dest = (s3_bucket, s3_folder)

            aws_device_type = self._device.type
            if aws_device_type == AwsDeviceType.SIMULATOR:
                self._device_type = _DeviceType.SIMULATOR
            elif aws_device_type == AwsDeviceType.QPU:
                self._device_type = _DeviceType.QPU
            else:
                raise ValueError(f"Unsupported device type {aws_device_type}")
        if self._verbatim and not aws_device_type == _DeviceType.QPU:
            raise ValueError(
                f"The `verbatim` argument is not supported for {aws_device_type}"
            )
        if self._verbatim and provider == "ionq":
            raise ValueError(
                "The `verbatim` argument is not yet supported for IonQ devices"
            )
        props = self._device.properties.dict()
        action = props["action"]
        device_info = action.get(DeviceActionType.JAQCD)
        if device_info is None:
            device_info = action.get(DeviceActionType.OPENQASM)
        if device_info is None:
            # This can happen with quantum anealers (e.g. D-Wave devices)
            raise ValueError(f"Unsupported device {device}")

        supported_ops = set(  # noqa: C401
            op.lower()
            for op in (
                props["paradigm"]["nativeGateSet"]
                if self._verbatim
                else device_info["supportedOperations"]
            )
        )
        supported_result_types = device_info["supportedResultTypes"]
        self._result_types = set()
        for rt in supported_result_types:
            rtname = rt["name"]
            rtminshots = rt["minShots"]
            rtmaxshots = rt["maxShots"]
            self._result_types.add(rtname)
            if rtname == "StateVector":
                self._supports_state = True
                # Always use n_shots = 0 for StateVector
            elif rtname == "Amplitude":
                pass  # Always use n_shots = 0 for Amplitude
            elif rtname == "Probability":
                self._probability_min_shots = rtminshots
                self._probability_max_shots = rtmaxshots
            elif rtname == "Expectation":
                self._supports_expectation = True
                self._expectation_allows_nonhermitian = False
                self._expectation_min_shots = rtminshots
                self._expectation_max_shots = rtmaxshots
            elif rtname == "Sample":
                self._supports_shots = True
                self._supports_counts = True
                self._supports_contextual_optimisation = True
                self._sample_min_shots = rtminshots
                self._sample_max_shots = rtmaxshots
            elif rtname == "Variance":
                self._variance_min_shots = rtminshots
                self._variance_max_shots = rtmaxshots
            elif rtname == "DensityMatrix":
                self._supports_density_matrix = True
                # Always use n_shots = 0 for DensityMatrix
        # Don't use contextual optimization for non-QPU backends
        if self._device_type != _DeviceType.QPU:
            self._supports_contextual_optimisation = False

        self._singleqs, self._multiqs = self._get_gate_set(
            supported_ops, self._device_type, self._verbatim
        )

        self._arch, self._all_qubits = self._get_arch_info(props, self._device_type)
        self._characteristics: dict | None = None
        if self._device_type == _DeviceType.QPU:
            self._characteristics = props["provider"]
        self._backend_info = self._get_backend_info(
            self._arch,
            device,
            self._singleqs,
            self._multiqs,
            self._characteristics,
        )

        n_qubits = len(self._all_qubits)

        self._supports_client_qubit_mapping = self._device_type == _DeviceType.QPU

        self._requires_all_qubits_measured = False
        try:
            if (self._device_type == _DeviceType.QPU) and props["action"][
                DeviceActionType.OPENQASM
            ]["requiresAllQubitsMeasurement"]:
                self._requires_all_qubits_measured = True
        except KeyError:
            pass

        self._req_preds = [
            NoClassicalControlPredicate(),
            NoFastFeedforwardPredicate(),
            NoMidMeasurePredicate(),
            NoSymbolsPredicate(),
            GateSetPredicate(self._multiqs | self._singleqs | {OpType.Measure}),
            MaxNQubitsPredicate(n_qubits),
        ]

        if self._device_type == _DeviceType.QPU and not isinstance(
            self._arch, FullyConnected
        ):
            self._req_preds.append(ConnectivityPredicate(self._arch))

        self._rebase_pass = AutoRebase(self._multiqs | self._singleqs)
        self._squash_pass = AutoSquash(self._singleqs)

    @staticmethod
    def _get_gate_set(
        supported_ops: set[str], device_type: _DeviceType, verbatim: bool
    ) -> tuple[set[OpType], set[OpType]]:
        multiqs = set()
        singleqs = set()
        if verbatim:
            for t in supported_ops:
                tkt = _gate_types[t]
                if tkt is not None:
                    if t in _multiq_gate_types:
                        multiqs.add(tkt)
                    else:
                        singleqs.add(tkt)
        else:
            if not {"cnot", "rx", "rz", "x"} <= supported_ops:
                # This is so that we can define AutoRebase without prior knowledge of the
                # gate set, and use X as the bit-flip gate in contextual optimization. We
                # could do better than this, by defining different options depending on the
                # supported gates. But it seems all existing backends support these gates.
                raise NotImplementedError(
                    "Device must support cnot, rx, rz and x gates."
                )
            for t in supported_ops:
                tkt = _gate_types[t]
                if tkt is not None:
                    if t in _multiq_gate_types:
                        if device_type == _DeviceType.QPU and t in ["ccnot", "cswap"]:
                            # FullMappingPass can't handle 3-qubit gates, so ignore them.
                            continue
                        multiqs.add(tkt)
                    else:
                        singleqs.add(tkt)
        return singleqs, multiqs

    @staticmethod
    def _get_arch_info(
        device_properties: dict[str, Any], device_type: _DeviceType
    ) -> tuple[Architecture | FullyConnected, list[int]]:
        # return the architecture, and all_qubits
        paradigm = device_properties["paradigm"]
        n_qubits = paradigm["qubitCount"]
        connectivity_graph = None  # None means "fully connected"
        if device_type == _DeviceType.QPU:
            connectivity = paradigm["connectivity"]
            if connectivity["fullyConnected"]:
                all_qubits: list = list(range(n_qubits))
            else:
                schema = device_properties["provider"]["braketSchemaHeader"]
                connectivity_graph = connectivity["connectivityGraph"]
                # Convert strings to ints
                if schema in (IQM_SCHEMA, RIGETTI_SCHEMA):
                    connectivity_graph = dict(  # noqa: C402
                        (int(k), [int(v) for v in l])
                        for k, l in connectivity_graph.items()
                    )
                    # each connectivity graph key will be an int
                    # connectivity_graph values will be lists
                    all_qubits_set = set()
                    for k, v in connectivity_graph.items():
                        all_qubits_set.add(k)
                        all_qubits_set.update(v)
                    all_qubits = list(all_qubits_set)
                else:
                    raise ValueError(f"Unsupported device schema {schema}")
        else:
            all_qubits = list(range(n_qubits))

        arch: Architecture | FullyConnected
        if connectivity_graph is None:
            arch = FullyConnected(len(all_qubits))
        else:
            arch = Architecture(
                [(k, v) for k, l in connectivity_graph.items() for v in l]
            )
        return arch, all_qubits

    @classmethod
    def _get_backend_info(
        cls,
        arch: Architecture | FullyConnected,
        device_name: str,
        singleqs: set[OpType],
        multiqs: set[OpType],
        characteristics: dict[str, Any] | None,
    ) -> BackendInfo:
        if characteristics is not None:
            schema = characteristics["braketSchemaHeader"]
            if schema == IONQ_SCHEMA:
                fid = characteristics["fidelity"]
                get_node_error: Callable[[Node], float] = lambda n: 1.0 - cast(
                    "float", fid["1Q"]["mean"]
                )
                get_readout_error: Callable[[Node], float] = lambda n: 0.0
                get_link_error: Callable[[Node, Node], float] = (
                    lambda n0, n1: 1.0 - cast("float", fid["2Q"]["mean"])
                )
            elif schema == RIGETTI_SCHEMA:
                specs = characteristics["specs"]
                benchmarks = specs["benchmarks"]
                instructions = specs["instructions"]
                specs1qrb = {}
                for benchmark in benchmarks[0]["sites"]:
                    node1q = str(benchmark["node_ids"])
                    specs1qrb[node1q] = benchmark["characteristics"][0]["error"]
                specs1qro = {}
                for instruction in instructions[3]["sites"]:
                    node1q = str(instruction["node_ids"])
                    specs1qro[node1q] = instruction["characteristics"][0]["value"]
                specs2q = {}
                for instruction in instructions[4]["sites"]:
                    node2q = str(instruction["node_ids"])
                    specs2q[node2q] = instruction["characteristics"][0]["error"]
                get_node_error = lambda n: cast("float", specs1qrb[f"[{n.index[0]}]"])
                get_readout_error = lambda n: 1.0 - cast(
                    "float", specs1qro[f"[{n.index[0]}]"]
                )
                get_link_error = lambda n0, n1: cast(
                    "float",
                    specs2q[
                        f"[{min(n0.index[0], n1.index[0])}, "
                        f"{max(n0.index[0], n1.index[0])}]"
                    ],
                )
            elif schema == IQM_SCHEMA:
                properties = characteristics["properties"]
                props1q = {}
                for key in properties["one_qubit"].keys():  # noqa: SIM118
                    node1q = str(int(key))
                    props1q[node1q] = properties["one_qubit"][key]
                props2q = {}
                for key in properties["two_qubit"].keys():  # noqa: SIM118
                    ind = key.index("-")
                    node2q1, node2q2 = (
                        str(int(key[:ind])),
                        str(int(key[ind + 1 :])),
                    )
                    props2q[node2q1 + "-" + node2q2] = properties["two_qubit"][key]
                get_node_error = lambda n: 1.0 - cast(
                    "float", props1q[f"{n.index[0]}"]["f1Q_simultaneous_RB"]
                )
                get_readout_error = lambda n: 1.0 - cast(
                    "float", props1q[f"{n.index[0]}"]["fRO"]
                )
                get_link_error = lambda n0, n1: 1.0 - cast(
                    "float",
                    props2q[
                        f"{min(n0.index[0], n1.index[0])}-{max(n0.index[0], n1.index[0])}"
                    ]["fCZ"],
                )

            # readout error as symmetric 2x2 matrix
            to_sym_mat: Callable[[float], list[list[float]]] = lambda x: [
                [1.0 - x, x],
                [x, 1.0 - x],
            ]
            node_errors = {
                node: {optype: get_node_error(node) for optype in singleqs}
                for node in arch.nodes
            }
            readout_errors = {
                node: to_sym_mat(get_readout_error(node)) for node in arch.nodes
            }

            # Construct a fake coupling map if we have a FullyConnected architecture,
            # otherwise use the coupling provided by the Architecture class.
            coupling: list[tuple[Node, Node]]
            if isinstance(arch, FullyConnected):
                # cast is needed as mypy does not know that we passed a fixed
                # integer to `permutations`.
                coupling = cast(
                    "list[tuple[Node, Node]]", list(permutations(arch.nodes, 2))
                )
            else:
                coupling = arch.coupling
            link_errors = {
                (n0, n1): {optype: get_link_error(n0, n1) for optype in multiqs}
                for n0, n1 in coupling
            }

            backend_info = BackendInfo(
                cls.__name__,
                device_name,
                __extension_version__,
                arch,
                singleqs.union(multiqs),
                all_node_gate_errors=node_errors,
                all_edge_gate_errors=link_errors,
                all_readout_errors=readout_errors,
            )
        else:
            backend_info = BackendInfo(
                cls.__name__,
                device_name,
                __extension_version__,
                arch,
                singleqs.union(multiqs),
            )
        return backend_info

    @property
    def required_predicates(self) -> list[Predicate]:
        return self._req_preds

    @property
    def verbatim(self) -> bool:
        return self._verbatim

    def rebase_pass(self) -> BasePass:
        if self.verbatim and self._device.provider_name == "Rigetti":
            passes = [AutoRebase({OpType.ISWAPMax, OpType.Rz, OpType.SX}), RxFromSX()]
            return SequencePass(passes)
        return self._rebase_pass

    def default_compilation_pass(self, optimisation_level: int = 2) -> BasePass:
        assert optimisation_level in range(3)
        if not self.verbatim:
            passes = [DecomposeBoxes()]
            if optimisation_level == 1:
                passes.append(SynthesiseTket())
            elif optimisation_level == 2:  # noqa: PLR2004
                passes.append(FullPeepholeOptimise())
            passes.append(self.rebase_pass())
            if (
                (self._device_type == _DeviceType.QPU)
                and (self.characterisation is not None)
                and (not self._requires_all_qubits_measured)
            ):
                arch = self.backend_info.architecture
                assert isinstance(arch, Architecture)
                passes.append(
                    CXMappingPass(
                        arch,
                        NoiseAwarePlacement(
                            arch,
                            **get_avg_characterisation(self.characterisation),  # type: ignore
                        ),
                        directed_cx=False,
                        delay_measures=True,
                    )
                )
                passes.append(NaivePlacementPass(arch))
                passes.append(self.rebase_pass())
                # If CX weren't supported by the device then we'd need to do another
                # rebase_pass here. But we checked above that it is.
            if optimisation_level == 1:
                passes.extend([RemoveRedundancies(), self._squash_pass])
            if optimisation_level == 2:  # noqa: PLR2004
                passes.extend(
                    [
                        CliffordSimp(False),
                        SynthesiseTket(),
                        self.rebase_pass(),
                        self._squash_pass,
                    ]
                )
        else:
            passes = [DecomposeBoxes(), FlattenRegisters()]
            if optimisation_level == 0:
                passes.append(
                    self.rebase_pass()
                )  # to satisfy MaxTwoQubitGatesPredicate
            if optimisation_level == 1:
                passes.append(SynthesiseTket())
            elif optimisation_level == 2:  # noqa: PLR2004
                passes.append(FullPeepholeOptimise())
                arch = self.backend_info.architecture
            if isinstance(self._arch, Architecture):
                passes.append(
                    CXMappingPass(
                        self._arch,
                        NoiseAwarePlacement(
                            self._arch,
                            **get_avg_characterisation(self.characterisation),  # type: ignore
                        ),
                        directed_cx=False,
                        delay_measures=True,
                    )
                )
                passes.append(NaivePlacementPass(self._arch))
            if optimisation_level == 2:  # noqa: PLR2004
                passes.append(KAKDecomposition(allow_swaps=False))
                passes.append(CliffordSimp(allow_swaps=False))
                passes.append(SynthesiseTket())
            passes.append(self.rebase_pass())
            passes.append(RemoveRedundancies())
        return SequencePass(passes)

    @property
    def _result_id_type(self) -> _ResultIdTuple:
        # task ID
        # json list of target qubits
        # stringified dict of measurements
        # whether state vector is wanted
        # whether density matrix is wanted
        # serialized ppcirc or "null"
        return (str, str, str, bool, bool, str)

    def _run(
        self, bkcirc: braket.circuits.Circuit, n_shots: int = 0, **kwargs: KwargTypes
    ) -> AwsQuantumTask | LocalQuantumTask:
        if self._device_type == _DeviceType.LOCAL:
            return self._device.run(bkcirc, shots=n_shots, **kwargs)
        if self.verbatim:
            bkcirc = braket.circuits.Circuit().add_verbatim_box(bkcirc)
        return self._device.run(
            bkcirc,
            self._s3_dest,
            shots=n_shots,
            disable_qubit_rewiring=self._supports_client_qubit_mapping,
            **kwargs,
        )

    def _to_bkcirc(
        self, circuit: Circuit
    ) -> tuple[braket.circuits.Circuit, list[int], dict[int, int]]:
        return tk_to_braket(
            circuit,
            mapped_qubits=(self._device_type == _DeviceType.QPU),
            forced_qubits=(
                self._all_qubits
                if (
                    self._requires_all_qubits_measured
                    and OpType.noop in self.backend_info.gate_set
                )
                else None
            ),
            force_ops_on_target_qubits=(OpType.noop in self.backend_info.gate_set),
        )

    def process_circuits(  # noqa: PLR0912
        self,
        circuits: Sequence[Circuit],
        n_shots: None | int | Sequence[int | None] = None,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> list[ResultHandle]:
        """
        Supported `kwargs`:

        * `postprocess`: apply end-of-circuit simplifications and classical
          postprocessing to improve fidelity of results (bool, default False)

        * `simplify_initial`: apply the pytket :py:meth:`pytket.passes.SimplifyInitial` pass to improve
          fidelity of results assuming all qubits initialized to zero (bool, default
          False)
        """
        circuits = list(circuits)
        n_shots_list = Backend._get_n_shots_as_list(  # noqa: SLF001
            n_shots, len(circuits), optional=True, set_zero=True
        )

        if not self.supports_shots and not self.supports_state:
            raise RuntimeError("Backend does not support shots or state")

        if any(
            map(  # noqa: C417
                lambda n: n > 0
                and (n < self._sample_min_shots or n > self._sample_max_shots),
                n_shots_list,
            )
        ):
            raise ValueError(
                "For sampling, n_shots must be between "
                f"{self._sample_min_shots} and {self._sample_max_shots}. "
                "For statevector simulation, omit this parameter."
            )

        if valid_check:
            self._check_all_circuits(circuits, nomeasure_warn=False)

        postprocess = kwargs.get("postprocess", False)
        simplify_initial = kwargs.get("simplify_initial", False)

        handles = []
        for circ, n_shots in zip(circuits, n_shots_list, strict=False):  # noqa: PLR1704
            want_state = (n_shots == 0) and self.supports_state
            want_dm = (n_shots == 0) and self.supports_density_matrix
            if postprocess:
                c0, ppcirc = prepare_circuit(circ, allow_classical=False)
                ppcirc_rep = ppcirc.to_dict()
            else:
                c0, ppcirc, ppcirc_rep = circ, None, None
            if self.supports_contextual_optimisation and simplify_initial:
                SimplifyInitial(allow_classical=False, create_all_qubits=True).apply(c0)
            bkcirc, target_qubits, measures = self._to_bkcirc(c0)
            if want_state:
                bkcirc.add_result_type(ResultType.StateVector())
            if want_dm:
                bkcirc.add_result_type(ResultType.DensityMatrix(target=bkcirc.qubits))
            if not bkcirc.instructions and len(circ.bits) == 0:
                task = None
            else:
                task = self._run(bkcirc, n_shots=n_shots)
            if self._device_type == _DeviceType.LOCAL:
                # Results are available now. Put them in the cache.
                if task is not None:
                    assert task.state() == "COMPLETED"
                    results = _get_result(
                        task, target_qubits, measures, want_state, want_dm, ppcirc
                    )
                else:
                    results = {"result": self.empty_result(circ, n_shots=n_shots)}
            else:
                # Task is asynchronous. Must wait for results.
                results = {}
            if task is not None:
                handle = ResultHandle(
                    task.id,
                    json.dumps(target_qubits),
                    json.dumps(list(measures.items())),
                    want_state,
                    want_dm,
                    json.dumps(ppcirc_rep),
                )
            else:
                handle = ResultHandle(
                    str(uuid4()),
                    json.dumps(target_qubits),
                    json.dumps(list(measures.items())),
                    False,
                    False,
                    json.dumps(None),
                )
            self._cache[handle] = results
            handles.append(handle)
        return handles

    def _update_cache_result(
        self, handle: ResultHandle, result_dict: dict[str, BackendResult]
    ) -> None:
        if handle in self._cache:
            self._cache[handle].update(result_dict)
        else:
            self._cache[handle] = result_dict

    def circuit_status(self, handle: ResultHandle) -> CircuitStatus:  # noqa: PLR0911
        if self._device_type == _DeviceType.LOCAL:
            return CircuitStatus(StatusEnum.COMPLETED)
        task_id, target_qubits, measures, want_state, want_dm, ppcirc_str = handle

        ppcirc_rep = json.loads(ppcirc_str)
        ppcirc = Circuit.from_dict(ppcirc_rep) if ppcirc_rep is not None else None
        task = AwsQuantumTask(task_id, aws_session=self._aws_session)
        state = task.state()
        if state == "FAILED":
            return CircuitStatus(StatusEnum.ERROR, task.metadata()["failureReason"])
        if state in ["CANCELLED", "CANCELLING"]:
            return CircuitStatus(StatusEnum.CANCELLED)
        if state == "COMPLETED":
            self._update_cache_result(
                handle,
                _get_result(
                    task,
                    json.loads(target_qubits),
                    dict(json.loads(measures)),
                    want_state,
                    want_dm,
                    ppcirc,
                ),
            )
            return CircuitStatus(StatusEnum.COMPLETED)
        if state == "QUEUED" or state == "CREATED":  # noqa: PLR1714
            return CircuitStatus(StatusEnum.QUEUED)
        if state == "RUNNING":
            return CircuitStatus(StatusEnum.RUNNING)
        return CircuitStatus(StatusEnum.ERROR, f"Unrecognized state '{state}'")

    @property
    def characterisation(self) -> dict[str, Any] | None:
        node_errors = self._backend_info.all_node_gate_errors
        edge_errors = self._backend_info.all_edge_gate_errors
        readout_errors = self._backend_info.all_readout_errors
        if node_errors is None and edge_errors is None and readout_errors is None:
            return None
        return {
            "NodeErrors": node_errors,
            "EdgeErrors": edge_errors,
            "ReadoutErrors": readout_errors,
        }

    @property
    def backend_info(self) -> BackendInfo:
        return self._backend_info

    @classmethod
    def available_devices(cls, **kwargs: Any) -> list[BackendInfo]:
        """
        See :py:meth:`pytket.backends.backend.Backend.available_devices`.
        Supported kwargs:

        - `region` (default None). The particular AWS region to search for
          devices (e.g. us-east-1). Default to the region configured with AWS.
          See the Braket docs for more details.
        - `aws_session` (default None). The credentials of the provided session
          will be used to create a new session with the specified region. Otherwise,
          a default new session will be created

        :return: A list of BackendInfo objects describing available devices.
        """
        region: str | None = kwargs.get("region")
        aws_session: AwsSession | None = kwargs.get("aws_session")
        verbatim: bool = cast("bool", kwargs.get("verbatim"))
        if aws_session is None:
            if region is not None:
                session = AwsSession(boto_session=boto3.Session(region_name=region))
            else:
                session = AwsSession()
        elif region is not None:
            session = aws_session.copy_session(region=region)
        else:
            session = aws_session.copy_session(region=aws_session.region)

        devices = session.search_devices(statuses=["ONLINE"])

        backend_infos = []

        for device in devices:
            aws_device = AwsDevice(device["deviceArn"], aws_session=session)
            if aws_device.type == AwsDeviceType.SIMULATOR:
                device_type = _DeviceType.SIMULATOR
            elif aws_device.type == AwsDeviceType.QPU:
                device_type = _DeviceType.QPU
            else:
                continue

            props = aws_device.properties.dict()
            try:
                device_info = props["action"][DeviceActionType.JAQCD]
                supported_ops = set(  # noqa: C401
                    op.lower() for op in device_info["supportedOperations"]
                )
                singleqs, multiqs = cls._get_gate_set(
                    supported_ops, device_type, verbatim
                )
            except KeyError:
                # The device has unsupported ops or it's a quantum annealer
                continue
            arch, _ = cls._get_arch_info(props, device_type)
            characteristics = None
            if device_type == _DeviceType.QPU:
                characteristics = props["provider"]
            backend_info = cls._get_backend_info(
                arch,
                device["deviceName"],
                singleqs,
                multiqs,
                characteristics,
            )
            backend_infos.append(backend_info)
        return backend_infos

    def get_result(self, handle: ResultHandle, **kwargs: KwargTypes) -> BackendResult:
        """
        See :py:meth:`pytket.backends.backend.Backend.get_result`.
        Supported kwargs: `timeout` (default none), `wait` (default 1s).
        """
        try:
            return super().get_result(handle)
        except CircuitNotRunError:
            timeout = cast("float", kwargs.get("timeout", 60.0))
            wait = cast("float", kwargs.get("wait", 1.0))
            # Wait for job to finish; result will then be in the cache.
            end_time = (time.time() + timeout) if (timeout is not None) else None
            while (end_time is None) or (time.time() < end_time):
                circuit_status = self.circuit_status(handle)
                if circuit_status.status is StatusEnum.COMPLETED:
                    return cast("BackendResult", self._cache[handle]["result"])
                if circuit_status.status is StatusEnum.ERROR:
                    raise RuntimeError(circuit_status.message)  # noqa: B904
                time.sleep(wait)
            raise RuntimeError(  # noqa: B904
                f"Timed out: no results after {timeout} seconds."
            )

    def _get_expectation_value(
        self,
        bkcirc: braket.circuits.Circuit,
        observable: Observable,
        target: QubitSet,
        n_shots: int,
        **kwargs: KwargTypes,
    ) -> np.float64:
        if not self.supports_expectation:
            raise RuntimeError("Backend does not support expectation")
        if (
            n_shots < self._expectation_min_shots
            or n_shots > self._expectation_max_shots
        ):
            raise ValueError(
                f"n_shots must be between {self._expectation_min_shots} and "
                f"{self._expectation_max_shots}"
            )
        restype = ResultType.Expectation(observable, target=target)
        bkcirc.add_result_type(restype)
        task = self._run(bkcirc, n_shots=n_shots, **kwargs)
        res = task.result()
        return res.get_value_by_result_type(restype)  # type: ignore

    @property
    def supports_variance(self) -> bool:
        """
        Whether the backend support calculation of operator variance
        """
        return "Variance" in self._result_types

    @property
    def supports_probability(self) -> bool:
        """
        Whether the backend support calculation of outcome probabilities
        """
        return "Probability" in self._result_types

    @property
    def supports_amplitude(self) -> bool:
        """
        Whether the backend support calculation of final state amplitudes
        """
        return "Amplitude" in self._result_types

    def _get_variance(
        self,
        bkcirc: braket.circuits.Circuit,
        observable: Observable,
        target: QubitSet,
        n_shots: int,
        **kwargs: KwargTypes,
    ) -> np.float64:
        if not self.supports_variance:
            raise RuntimeError("Backend does not support variance")
        if n_shots < self._variance_min_shots or n_shots > self._variance_max_shots:
            raise ValueError(
                f"n_shots must be between {self._variance_min_shots} and "
                f"{self._variance_max_shots}"
            )
        restype = ResultType.Variance(observable, target=target)
        bkcirc.add_result_type(restype)
        task = self._run(bkcirc, n_shots=n_shots, **kwargs)
        res = task.result()
        return res.get_value_by_result_type(restype)  # type: ignore

    def get_pauli_expectation_value(
        self,
        state_circuit: Circuit,
        pauli: QubitPauliString,
        n_shots: int = 0,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> np.float64:
        """
        Compute the (exact or empirical) expectation of the observed eigenvalues.

        See :py:func:`pytket.utils.get_pauli_expectation_value`.

        If `n_shots > 0` the probabilities are calculated empirically by measurements.
        If `n_shots = 0` (if supported) they are calculated exactly by simulation.

        Supported `kwargs` (not valid for local simulator):

        - `poll_timeout_seconds` (int) : Polling timeout for synchronous retrieval of
          result, in seconds (default: 5 days).
        - `poll_interval_seconds` (int) : Polling interval for synchronous retrieval of
          result, in seconds (default: 1 second).

        :return: :math:`\\left<\\psi | P | \\psi \\right>`
        """
        if valid_check:
            self._check_all_circuits([state_circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(state_circuit)
        observable, qbs = _obs_from_qps(state_circuit, pauli)
        return self._get_expectation_value(bkcirc, observable, qbs, n_shots, **kwargs)

    def get_operator_expectation_value(
        self,
        state_circuit: Circuit,
        operator: QubitPauliOperator,
        n_shots: int = 0,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> np.float64:
        """
        Compute the (exact or empirical) expectation of the observed eigenvalues.

        See :py:func:`pytket.utils.get_operator_expectation_value`.

        If `n_shots > 0` the probabilities are calculated empirically by measurements.
        If `n_shots = 0` (if supported) they are calculated exactly by simulation.

        Supported `kwargs` are as for :py:meth:`~.BraketBackend.get_pauli_expectation_value`.
        """
        if valid_check:
            self._check_all_circuits([state_circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(state_circuit)
        observable = _obs_from_qpo(operator, state_circuit.n_qubits)
        return self._get_expectation_value(
            bkcirc, observable, bkcirc.qubits, n_shots, **kwargs
        )

    def get_pauli_variance(
        self,
        state_circuit: Circuit,
        pauli: QubitPauliString,
        n_shots: int = 0,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> np.float64:
        """
        Compute the (exact or empirical) variance of the observed eigenvalues.

        See :py:func:`pytket.utils.get_pauli_expectation_value`.

        If `n_shots > 0` the probabilities are calculated empirically by measurements.
        If `n_shots = 0` (if supported) they are calculated exactly by simulation.

        Supported `kwargs` are as for :py:meth:`~.BraketBackend.get_pauli_expectation_value`.
        """
        if valid_check:
            self._check_all_circuits([state_circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(state_circuit)
        observable, qbs = _obs_from_qps(state_circuit, pauli)
        return self._get_variance(bkcirc, observable, qbs, n_shots, **kwargs)

    def get_operator_variance(
        self,
        state_circuit: Circuit,
        operator: QubitPauliOperator,
        n_shots: int = 0,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> np.float64:
        """
        Compute the (exact or empirical) variance of the observed eigenvalues.

        See :py:func:`pytket.utils.get_operator_expectation_value`.

        If `n_shots > 0` the probabilities are calculated empirically by measurements.
        If `n_shots = 0` (if supported) they are calculated exactly by simulation.

        Supported `kwargs` are as for :py:meth:`~.BraketBackend.get_pauli_expectation_value`.
        """
        if valid_check:
            self._check_all_circuits([state_circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(state_circuit)
        observable = _obs_from_qpo(operator, state_circuit.n_qubits)
        return self._get_variance(bkcirc, observable, bkcirc.qubits, n_shots, **kwargs)

    def get_probabilities(
        self,
        circuit: Circuit,
        qubits: Iterable[int] | None = None,
        n_shots: int = 0,
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> np.ndarray:
        """
        Compute the (exact or empirical) probability distribution of outcomes.

        If `n_shots > 0` the probabilities are calculated empirically by measurements.
        If `n_shots = 0` (if supported) they are calculated exactly by simulation.

        Supported `kwargs` are as for :py:meth:`~.BraketBackend.process_circuits`.

        The order is big-endian with respect to the order of qubits in the argument.
        For example, if qubits=[0,1] then the order of probabilities is [p(0,0), p(0,1),
        p(1,0), p(1,1)], while if qubits=[1,0] the order is [p(0,0), p(1,0), p(0,1),
        p(1,1)], where p(i,j) is the probability of qubit 0 being in state i and qubit 1
        being in state j.

        :param qubits: qubits of interest

        :returns: list of probabilities of outcomes if initial state is all-zeros
        """
        if not self.supports_probability:
            raise RuntimeError("Backend does not support probability")
        if (
            n_shots < self._probability_min_shots
            or n_shots > self._probability_max_shots
        ):
            raise ValueError(
                f"n_shots must be between {self._probability_min_shots} and "
                f"{self._probability_max_shots}"
            )
        if valid_check:
            self._check_all_circuits([circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(circuit)
        restype = ResultType.Probability(target=qubits)
        bkcirc.add_result_type(restype)
        task = self._run(bkcirc, n_shots=n_shots, **kwargs)
        res = task.result()
        return res.get_value_by_result_type(restype)  # type: ignore

    def get_amplitudes(
        self,
        circuit: Circuit,
        states: list[str],
        valid_check: bool = True,
        **kwargs: KwargTypes,
    ) -> dict[str, complex]:
        """
        Compute the complex coefficients of the final state.

        Supported `kwargs` are as for :py:meth:`~.BraketBackend.process_circuits`.

        :param states: classical states of interest, as binary strings of '0' and '1'

        :returns: final complex amplitudes if initial state is all-zeros
        """
        if not self.supports_amplitude:
            raise RuntimeError("Backend does not support amplitude")
        if valid_check:
            self._check_all_circuits([circuit], nomeasure_warn=False)
        bkcirc, _target_qubits, _measures = self._to_bkcirc(circuit)
        restype = ResultType.Amplitude(states)
        bkcirc.add_result_type(restype)
        task = self._run(bkcirc, n_shots=0, **kwargs)
        res = task.result()
        amplitudes = res.get_value_by_result_type(restype)
        cdict = {}
        for k, v in amplitudes.items():
            # The amazon/sv1 simulator gives us 2-element lists [re, im].
            # The local simulator gives us numpy.complex128.
            cdict[k] = complex(*v) if type(v) is list else complex(v)
        return cdict

    def cancel(self, handle: ResultHandle) -> None:
        if self._device_type == _DeviceType.LOCAL:
            raise NotImplementedError("Circuits on local device cannot be cancelled")
        task_id = handle[0]
        task = AwsQuantumTask(task_id, aws_session=self._aws_session)
        if task.state() != "COMPLETED":
            task.cancel()
