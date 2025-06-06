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

from dataclasses import dataclass
from typing import Any, ClassVar

from pytket.config import PytketExtConfig


@dataclass
class BraketConfig(PytketExtConfig):
    """Holds config parameters for pytket-braket."""

    ext_dict_key: ClassVar[str] = "braket"

    s3_bucket: str | None
    s3_folder: str | None
    device_type: str | None
    provider: str | None

    @classmethod
    def from_extension_dict(
        cls: type["BraketConfig"], ext_dict: dict[str, Any]
    ) -> "BraketConfig":
        return cls(
            ext_dict.get("s3_bucket"),
            ext_dict.get("s3_folder"),
            ext_dict.get("device_type"),
            ext_dict.get("provider"),
        )


def set_braket_config(
    s3_bucket: str | None = None,
    s3_folder: str | None = None,
    device_type: str | None = None,
    provider: str | None = None,
) -> None:
    """Set default values for any of s3_bucket, s3_folder, device_type or provider
    for AWS Braket. Can be overridden in backend construction."""
    config = BraketConfig.from_default_config_file()
    if s3_bucket is not None:
        config.s3_bucket = s3_bucket
    if s3_folder is not None:
        config.s3_folder = s3_folder
    if device_type is not None:
        config.device_type = device_type
    if provider is not None:
        config.provider = provider
    config.update_default_config_file()
