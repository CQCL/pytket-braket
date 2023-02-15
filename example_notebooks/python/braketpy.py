# ## AWS via pytket

# This notebook describes how to how to run a simple circuit using the `pytket-braket` backend from scratch.

# ### Prerequisites

# #### Python packages:

# - `pytket`'s extension for Amazon Braket devices [pytket-braket](https://pypi.org/project/pytket-braket/)
#     - `pip install pytket-braket`
# - Amazon's braket package [amazon-braket-sdk](https://pypi.org/project/amazon-braket-sdk/)
#     - `pip install amazon-braket-sdk`
# - `boto3`, which is Amazon's package for accessing AWS (so called because Boto dolphins live in the Amazon 🙄) [boto3](https://pypi.org/project/boto3/)
#     - `pip install boto3`


# ### What are we doing?

# There is a hierarchy of things we need to access here, as illustrated below. Amazon Web Services (AWS) contains many things, one of which is Amazon Braket. That in turn contains many quantum devices we can run things on.

# Essentially we nest interfaces from the three packages above to access each layer of services:
# $$
# \textrm{amazon web services} \rightarrow \textrm{amazon braket} \rightarrow \textrm{quantum device}
# $$


# ![Alt text](aws_img_w.png)


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

# #### Create a credentials file
# - Finally, in the directory you're working in, create a file with the following format, and name it somethign sensible like `aws_creds.txt`:

#     aws_access_key_id
#     aws_secret_access_key
#     s3_name [i.e. the name of your bucket]
#     bucket_key [i.e. the name of the folder you created in the bucket]
    

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
my_region = 'eu-west-2'
my_s3_bucket = 'amazon-braket-example'

# Read in credentials from the file created earlier
with open('aws_cred.txt', 'r') as f:
    aws_access_key_id, aws_secret_access_key, s3_name, bucket_key =\
        [s.strip() for s in f.readlines()]

# Access AWS with boto3, and pass the session to braket
my_boto_session = boto3.Session(aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key,
                                region_name=my_region)
                                
my_aws_session = AwsSession(boto_session=my_boto_session)

# Print devices available in our region
[x.device_name for x in BraketBackend.available_devices(region=my_region,
                                                        aws_session=my_aws_session)]


# Initialise BraketBackend for OQC device
aws_oqc_backend = BraketBackend(local=False,
                                region=my_region,
                                device='Lucy',
                                s3_bucket=s3_name,
                                s3_folder=bucket_key,
                                device_type='qpu',
                                provider='oqc',
                                aws_session=my_aws_session)
                                
# Compile circuit for device:
compiled_circ = aws_oqc_backend.get_compiled_circuit(circ,2)
print("Valid circuit: ", aws_oqc_backend.valid_circuit(compiled_circ))

oqc_handle = aws_oqc_backend.process_circuit(compiled_circ, n_shots=500)
oqc_result = aws_oqc_backend.get_result(oqc_handle, timeout=None)

oqc_result.get_counts()

# Congratulations, you've successfully run a circuit with Amazon Braket and pytket!