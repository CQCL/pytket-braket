.. currentmodule:: pytket.extensions.braket

Changelog
~~~~~~~~~

0.39.0 (January 2025)
---------------------

* Updated pytket version requirement to 1.39.
* Remove code related to OQC devices (no longer supported on AWS Braket).

0.38.0 (October 2024)
---------------------

* Updated pytket version requirement to 1.33.

0.37.0 (July 2024)
------------------

* Updated pytket version requirement to 1.30.

0.36.0 (April 2024)
-------------------

* Updated pytket version requirement to 1.27.
* Devices with full connectivity will use the `FullyConnected` class
  to represent their architecture.

0.35.1 (March 2024)
-------------------

* Updated pytket version requirement to 1.26.

0.34.1 (January 2024)
---------------------

* Updated pytket version requirement to 1.24.
* Python 3.12 support added, 3.9 dropped.

0.33.0 (January 2024)
---------------------

* Updated pytket version requirement to 1.23.

0.32.0 (November 2023)
----------------------

* Updated pytket version requirement to 1.22.

0.31.2 (November 2023)
----------------------

* Replace uses of "private" (underscored) pytket symbols.

0.31.1 (October 2023)
---------------------

* Fix use of ``SimplifyInitial``

0.31.0 (October 2023)
---------------------

* Don't include ``SimplifyInitial`` in default passes; instead make it an option
  to ``process_circuits()``.
* Updated pytket version requirement to 1.21.

0.30.0 (September 2023)
-----------------------

* Update pytket version requirement to 1.19.
* Update amazon-braket-sdk version requirement to 1.53.
* Update amazon-braket-schemas version requirement to 1.19.
* Update amazon-braket-default-simulator version requirement to 1.20.

0.29.0 (July 2023)
------------------

* Update pytket version requirement to 1.17.

0.28.0 (June 2023)
------------------

* Updated pytket version requirement to 1.16.

0.27.0 (May 2023)
-----------------

* Updated pytket version requirement to 1.15.

0.26.0 (January 2023)
---------------------

* Drop support for Python 3.8; add support for 3.11.
* Fix handling of implicit qubit permutation for state simulators.
* Updated pytket version requirement to 1.11.

0.25.0 (November 2022)
----------------------

* Updated pytket version requirement to 1.9.

0.24.0 (November 2022)
----------------------

* Require circuits submitted to IonQ to have contiguous qubit numbering.
* Updated pytket version requirement to 1.8.

0.23.0 (October 2022)
---------------------

* Updated pytket version requirement to 1.7.

0.22.1 (September 2022)
-----------------------

* Ignore ``OpType.Barrier`` when converting to braket circuit.
* Fix results parsing when not all qubits are measured.
* Include all qubits in circuit when device requires it.

0.22.0 (September 2022)
-----------------------

* Fix tracking of qubit indices on devices with non-contiguous qubit sets.
* Update dependencies.
* Updated pytket version requirement to 1.6.

0.21.0 (July 2022)
------------------

* Updated pytket version requirement to 1.4.

0.20.0 (June 2022)
------------------

* Updated pytket version requirement to 1.3.

0.19.1 (June 2022)
------------------

* Fixes to qubit index handling.

0.19.0 (May 2022)
-----------------

* Add optional "aws_session" parameter to the available_devices class method of BracketBackend.
* Respect measurement operations in submitted circuits. (Previously these were
  not allowed and measurements were automatically added to all qubits.)
* Updated pytket version requirement to 1.2.

0.18.0 (April 2022)
-------------------

* Allow user to specify different local backends.
* Fix dimension mismatch for measurements for Braket QPU results.
* Updated pytket version requirement to 1.1.

0.17.0 (March 2022)
-------------------

* Add optional "region" argument for initializing BraketBackend.
* Update requirements for amazon-braket-sdk and amazon-braket-schemas.
* Add support for oqc provider.
* Correct readout errors reported for Rigetti devices.
* Add support for density-matrix simulators.
* Updated pytket version requirement to 1.0.

0.16.0 (February 2022)
----------------------

* Updated pytket version requirement to 0.19.
* Drop support for Python 3.7; add support for 3.10.
* Add support for CV gates.

0.15.0 (January 2022)
---------------------

* Updated pytket version requirement to 0.18.

0.14.0 (November 2021)
----------------------

* Updated pytket version requirement to 0.17.

0.13.0 (October 2021)
---------------------

* Updated pytket version requirement to 0.16.

0.12.0 (September 2021)
-----------------------

* Updated pytket version requirement to 0.15.

0.11.0 (September 2021)
-----------------------

* Updated pytket version requirement to 0.14.

0.10.0 (July 2021)
------------------

* Updated pytket version requirement to 0.13.

0.9.0 (June 2021)
-----------------

* Updated pytket version requirement to 0.12.

0.8.2 (June 2021)
-----------------

* Make cache handling more robust.

0.8.1 (June 2021)
-----------------

* Make BracketBackend.device a property, in accordance with definition in base class.

0.8.0 (May 2021)
----------------

* Updated pytket version requirement to 0.11.

0.7.0 (May 2021)
----------------

* Contextual optimisation added to default compilation passes (except at optimisation level 0).
