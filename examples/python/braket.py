# ## AWS via pytket

# This notebook describes how to how to run a simple circuit using the `pytket-braket` backend from scratch.

# ### Prerequisites

# #### Python packages:

# - `boto3`, which is Amazon's package for accessing AWS (so called because Boto dolphins live in the Amazon 🙄) [boto3](https://pypi.org/project/boto3/)
# - `amazon-braket-sdk`, which is Amazon's braket package [amazon-braket-sdk](https://pypi.org/project/amazon-braket-sdk/)
# - `pytket`'s extension for Amazon Braket devices [pytket-braket](https://pypi.org/project/pytket-braket/)

# To install these, you can run the following:
#    `pip install pytket-braket boto3`
# (`pytket-braket` has `amazon-braket-sdk` as a dependency, so you don't need to install that separately)

# ### What are we doing?

# There is a hierarchy of things we need to access here, as illustrated below. Amazon Web Services (AWS) contains many things, one of which is Amazon Braket. That in turn contains many quantum devices we can run things on.

# Essentially we nest interfaces from the three packages above to access each layer of services:
# $$ \textrm{amazon web services} \rightarrow \textrm{amazon braket} \rightarrow \textrm{quantum device} $$

# <div>
# <img src="python/aws_img.png" width="500"/>
# </div>

# ### Credentials

# You need the following credentials to access devices with AWS:
# - AWS account ID (12 digits) or account alias
# - User name
# - Password

# And for accessing services in python, a public and private key:
# - AWS access key ID
# - AWS secret access key


# ### What is S3?

# Amazon has a Dropbox-like service called Amazon S3 -- Simple Storage Service. This is a service under the AWS umbrella where results from experiments can be saved. These are saved in top-level folders called 'S3 buckets'.


# ### Setting up AWS

# #### Checking the region for the device you want
# - Find Amazon Braket and go to 'Devices'
# - Check the `region` for the device you want to access (e.g. for OQC's Lucy device, this is `eu-west-2`)

# #### Create an S3 bucket
# - Under AWS, go to Amazon S3 and create a new bucket and choose a `name` and the `region` from above. __NOTE:__ the `name` __must__ start with the prefix `amazon-braket`, e.g. `amazon-braket-my-test-experiment`!
# - Once you've created the bucket, select it and create a folder inside. In python, the name of this folder becomes known as the `bucket_key`.

# #### Set up your credentials
# - Finally, follow the instructions [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html) to create a credentials file. This can be done using the `aws configure` command in the terminal once you've `pip`-installed the `aws-shell` package.
# - You can create multiple profiles this way, but as standard you can pass `profile-name=default` to load your credentials, as we'll see below.
# - You can also set defaults such as `s3_bucket` and `s3_folder` in the `~/.config/pytket/config.json` file so you don't have to pass them in manually:
# ```
# "extensions": {
#  "braket": {
#    "region": "eu-west-2",
#    "s3_bucket": "amazon-braket-my-bucket-name",
#    "s3_folder": "my-folder-name"
#  }
# }
# ```

# ### Running a circuit

# For the purposes of this example, we'll assume that you've created the files above, and that we want to access OQC's Lucy quantum device.

# Circuit construction
from pytket import Circuit
from pytket.circuit.display import render_circuit_jupyter as rcj
from pytket.extensions.braket import tk_to_braket
from pytket.extensions.braket import BraketBackend

# Accessing AWS
import boto3
from braket.aws.aws_session import AwsSession

# Define a simple circuit:
n_qubits = 2
circ = Circuit(2)
circ.H(0)
circ.CX(0, 1)
circ.measure_all()

rcj(circ)

# Use region and bucket defined in AWS earlier
my_region = "eu-west-2"

# Access AWS with boto3, and pass the session to braket
my_boto_session = boto3.Session(profile_name="default")

my_aws_session = AwsSession(boto_session=my_boto_session)

# Print devices available in our region
[
    x.device_name
    for x in BraketBackend.available_devices(
        region=my_region, aws_session=my_aws_session
    )
]

# Initialise BraketBackend for OQC device
aws_oqc_backend = BraketBackend(
    local=False,
    region="eu-west-2",
    device="Lucy",
    device_type="qpu",
    provider="oqc",
)


# Compile circuit for device:
compiled_circ = aws_oqc_backend.get_compiled_circuit(circ, 2)
print("Valid circuit: ", aws_oqc_backend.valid_circuit(compiled_circ))

oqc_handle = aws_oqc_backend.process_circuit(compiled_circ, n_shots=500)
oqc_result = aws_oqc_backend.get_result(oqc_handle, timeout=None)

oqc_result.get_counts()

# Congratulations, you've successfully run a circuit with Amazon Braket and pytket!
