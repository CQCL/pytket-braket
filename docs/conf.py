# -*- coding: utf-8 -*-
import os

# Configuration file for the Sphinx documentation builder.
# See https://www.sphinx-doc.org/en/master/usage/configuration.html

copyright = "2025 Quantinuum"
author = "Quantinuum"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "enum_tools.autoenum",
    "sphinx.ext.autosectionlabel",
    "myst_nb",
    "sphinxcontrib.googleanalytics",
    "quantinuum_sphinx"
]

nitpicky = True

nitpick_ignore = {
    # nanobind signatures for arrays and JSON do not generate references
    ("py:class", "numpy.ndarray[dtype=complex128, shape=(*, *), order='F']"),
    ("py:class", "numpy.ndarray[dtype=complex128, shape=(2, 2), order='F']"),
    ("py:class", "numpy.ndarray[dtype=complex128, shape=(4, 4), order='F']"),
    ("py:class", "numpy.ndarray[dtype=complex128, shape=(8, 8), order='F']"),
    ("py:class", "numpy.ndarray[dtype=complex128, shape=(*), order='C']"),
    ("py:class", "JSON"),
    # numpy type aliases are documented as data rather than classes, so when 
    # used in signatures sphinx cannot find the cross-reference as it only 
    # looks for classes
    ("py:class", "numpy.typing.ArrayLike"),
    # similar for our own type aliases
    ("py:class", "pytket.utils.distribution.T0"),
    # some packages don't expose all of their classes
    ("py:class", "qiskit_aer.backends.aerbackend.AerBackend"),
    ("py:class", "qiskit_aqt_provider.api_client.models_generated.JobResponseRRQueued"),
    ("py:class", "qiskit_aqt_provider.api_client.models_generated.JobResponseRROngoing"),
    ("py:class", "qiskit_aqt_provider.api_client.models_generated.JobResponseRRFinished"),
    ("py:class", "qiskit_aqt_provider.api_client.models_generated.JobResponseRRError"),
    ("py:class", "qiskit_aqt_provider.api_client.models_generated.JobResponseRRCancelled"),
    ("py:class", "qiskit_ibm_runtime.models.backend_configuration.QasmBackendConfiguration"),
    ("py:class", "qiskit_ibm_runtime.models.backend_properties.BackendProperties"),
    ("py:class", "qujax.utils.CallableArrayAndOptionalArray"),
    ("py:class", "qujax.utils.CallableOptionalArray"),
    # some other packages it is difficult to link to
    ("py:class", "pathlib._local.Path"),
    ("py:class", "jinja2.nodes.Output"),
    ("py:class", "numpy.float64"),
    ("py:class", "qulacs_core.QuantumCircuit"),
    ("py:class", "Value"), # pyqir.Value cannot be found
    # matplotlib not always installed and referred to using a string name in pytket-quantinuum
    ("py:class", "matplotlib.figure.Figure"),
}

nitpick_ignore_regex = {
    # cirq appears to no longer use sphinx, so every cross-ref will fail
    ("py:.*", "cirq.*"),
    # no online docs found for mtkahypar (used in pytket-aqt)
    ("py:.*", "mtkahypar.*"),
}

autodoc_type_aliases = {
    "npt.ArrayLike": "numpy.typing.ArrayLike",
    "cp.ndarray": "cupy.ndarray",
}

linkcheck_ignore = [
    "https://github.com/CQCL/tket#how-to-build-tket-and-pytket",
    "https://quantumcomputing.stackexchange.com/questions/tagged/pytket",
    "https://tketusers.slack.com/join/shared_invite/zt-18qmsamj9-UqQFVdkRzxnXCcKtcarLRA#/shared-invite/email",
]

autosectionlabel_prefix_document = True

myst_enable_extensions = [
    "dollarmath",
    "html_image",
    "attrs_inline",
    "colon_fence",
    "amsmath",
]

# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html#auto-generated-header-anchors
myst_heading_anchors = 3

html_theme_options = {}

html_theme = "quantinuum_sphinx"
templates_path = ["_templates"]
html_static_path = ["_static"]
html_favicon = "_static/assets/quantinuum_favicon.svg"


pytketdoc_base = "https://docs.quantinuum.com/tket/"
ext_url = pytketdoc_base + "extensions/"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "jax": ("https://docs.jax.dev/en/latest", None),
    "sympy": ("https://docs.sympy.org/latest/", None),
    "scipy": ("https://docs.scipy.org/doc/scipy/", None),
    "networkx": ("https://networkx.org/documentation/stable/", None),
    "graphviz": ("https://graphviz.readthedocs.io/en/stable", None),
    "qiskit": ("https://docs.quantum.ibm.com/api/qiskit", None),
    "qiskit_ibm_runtime": ("https://docs.quantum.ibm.com/api/qiskit-ibm-runtime", None),
    "qiskit_aer": ("https://qiskit.github.io/qiskit-aer", None),
    "braket": ("https://amazon-braket-sdk-python.readthedocs.io/en/latest", None),
    "iqm": ("https://iqm-finland.github.io/iqm-client/", None),
    "pennylane": ("https://docs.pennylane.ai/en/stable", None),
    "projectq": ("https://projectq.readthedocs.io/en/latest", None),
    "pyquil": ("https://pyquil-docs.rigetti.com/en/stable", None),
    "pyzx": ("https://pyzx.readthedocs.io/en/latest", None),
    "pytket": (pytketdoc_base + "api-docs/", None),
    "pytket-qiskit": (ext_url + "pytket-qiskit/", None),
    "pytket-quantinuum": (
        ext_url + "pytket-quantinuum/",
        None,
    ),
    "pytket-pennylane": (ext_url + "pytket-pennylane/", None),
    "pytket-qujax": (ext_url + "pytket-qujax/", None),
    "pytket-cirq": (ext_url + "pytket-cirq/", None),
    "pytket-braket": (ext_url + "pytket-braket/", None),
    "pytket-pyquil": (ext_url + "pytket-pyquil/", None),
    "pytket-pysimplex": (ext_url + "pytket-pysimplex/", None),
    "pytket-projectq": (ext_url + "pytket-projectq/", None),
    "pytket-qulacs": (ext_url + "pytket-qulacs/", None),
    "pytket-iqm": (ext_url + "pytket-iqm/", None),
    "pytket-stim": (ext_url + "pytket-stim/", None),
    "pytket-quest": (ext_url + "pytket-quest/", None),
}

# Bit of a hack to avoid executing cutensornet notebooks (needs GPUs)
# The pytket-azure examples will also not be executable
# -------------------------------------------------------------------

# Get the current working directory
current_directory = os.getcwd()

# Get the parent directory (absolute path)
parent_directory = os.path.dirname(current_directory)

repo_name = os.path.split(parent_directory)[1]

# Don't execute pytket-cutensornet + pytket-azure examples, execute everything else.
if repo_name in ("pytket-cutensornet", "pytket-azure"):
    nb_execution_mode = "off"
else:
    nb_execution_mode = "cache"
# -------------------------------------------------------------------

if repo_name == "pytket":
    coverage_modules = ["pytket"]
    coverage_ignore_functions = ["add_wasm", "add_wasm_to_reg", "add_clexpr_from_logicexp"]
    coverage_ignore_modules = ["libtket", "libtklog", "pytket.extensions", "pytket.qir"]
elif repo_name == "pytket-qir":
    coverage_modules = ["pytket.qir"]
else:
    extension_name = repo_name[7:] # remove "pytket-" prefix
    coverage_modules = ["pytket.extensions." + extension_name]
coverage_statistics_to_stdout = False
coverage_show_missing_items = True
coverage_ignore_classes = []

nb_execution_timeout = 120

nb_execution_excludepatterns = [
    "examples/backends/backends_example.ipynb",
    "examples/backends/qiskit_integration.ipynb",
    "examples/backends/comparing_simulators.ipynb",
    "examples/algorithms_and_protocols/expectation_value_example.ipynb",
    "examples/algorithms_and_protocols/pytket-qujax_heisenberg_vqe.ipynb",
    "examples/algorithms_and_protocols/pytket-qujax-classification.ipynb",
    "examples/algorithms_and_protocols/pytket-qujax_qaoa.ipynb",
    "examples/algorithms_and_protocols/ucc_vqe.ipynb",
    "examples/algorithms_and_protocols/entanglement_swapping.ipynb",
]

exclude_patterns = [
    "**/jupyter_execute",
    "jupyter_execute/*",
    ".jupyter_cache",
    "*.venv",
    "README.md",
    "**/README.md",
    ".jupyter_cache",
]

autodoc_member_order = "groupwise"
googleanalytics_id = "G-YPQ1FTGDL3"
