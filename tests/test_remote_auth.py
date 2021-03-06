import requests
import docker
import pytest
import time
from random import SystemRandom
from os.path import join, dirname, realpath
from docker.types import Mount

IMAGE_NAME = "jupyterhub"
IMAGE_TAG = "test"
IMAGE = "".join([IMAGE_NAME, ":", IMAGE_TAG])

# root dir
docker_path = dirname(dirname(realpath(__file__)))

# mount paths
remote_config_path = join(
    dirname(realpath(__file__)), "jupyterhub_configs", "remote_auth_config.py"
)

# image build
jhub_image = {"path": docker_path, "tag": IMAGE, "rm": "True", "pull": "True"}

rand_key = "".join(SystemRandom().choice("0123456789abcdef") for _ in range(32))

target_config = "/etc/jupyterhub/jupyterhub_config.py"
# container cmd
jhub_cont = {
    "image": IMAGE,
    "name": IMAGE_NAME,
    "mounts": [
        Mount(
            source=remote_config_path, target=target_config, read_only=True, type="bind"
        )
    ],
    "ports": {8000: 8000},
    "detach": "True",
}


@pytest.mark.parametrize("build_image", [jhub_image], indirect=["build_image"])
@pytest.mark.parametrize("container", [jhub_cont], indirect=["container"])
def test_auth_hub(build_image, container):
    """
    Test that the client is able to,
    Not access the home path without being authed
    Authenticate with the Remote-User header
    """
    # not ideal, wait for the jhub container to start, update with proper check
    time.sleep(5)
    client = docker.from_env()
    containers = client.containers.list()
    assert len(containers) > 0
    session = requests.session()

    jhub_base_url = "http://127.0.0.1:8000/hub"
    # wait for jhub to be ready
    jhub_ready = False
    while not jhub_ready:
        resp = session.get("".join([jhub_base_url, "/home"]))
        if resp.status_code != 404:
            jhub_ready = True

    # Not allowed, -> not authed
    no_auth_response = session.get("".join([jhub_base_url, "/home"]))
    assert no_auth_response.status_code == 401

    # Auth requests
    user_cert = "/C=DK/ST=NA/L=NA/O=NBI/OU=NA/CN=Name" "/emailAddress=mail@sdfsf.com"
    other_user = "idfsf"

    cert_auth_header = {"Remote-User": user_cert}

    other_auth_header = {"Remote-User": other_user}

    auth_response = session.post(
        "".join([jhub_base_url, "/login"]), headers=cert_auth_header
    )
    assert auth_response.status_code == 200

    auth_response = session.get(
        "".join([jhub_base_url, "/home"]), headers=other_auth_header
    )
    assert auth_response.status_code == 200


@pytest.mark.parametrize("build_image", [jhub_image], indirect=["build_image"])
@pytest.mark.parametrize("container", [jhub_cont], indirect=["container"])
def test_auth_data_header(build_image, container):
    """
    Test that the client is able to.
    Once authenticated, pass a correctly formatted custom Data header
    """
    # not ideal, wait for the jhub container to start, update with proper check
    time.sleep(5)
    client = docker.from_env()
    containers = client.containers.list()
    assert len(containers) > 0
    session = requests.session()

    jhub_base_url = "http://127.0.0.1:8000/hub"
    # wait for jhub to be ready
    jhub_ready = False
    while not jhub_ready:
        resp = session.get("".join([jhub_base_url, "/home"]))
        if resp.status_code != 404:
            jhub_ready = True

    no_auth_mount = session.post("".join([jhub_base_url, "/data"]))
    assert no_auth_mount.status_code == 403

    # Auth requests
    user_cert = "/C=DK/ST=NA/L=NA/O=NBI/OU=NA/CN=Name" "/emailAddress=mail@sdfsf.com"

    cert_auth_header = {"Remote-User": user_cert}

    auth_response = session.get(
        "".join([jhub_base_url, "/home"]), headers=cert_auth_header
    )
    assert auth_response.status_code == 200

    auth_response = session.post(
        "".join([jhub_base_url, "/login"]), headers=cert_auth_header
    )
    assert auth_response.status_code == 200

    wrong_header = {"Mount": "SDfssdfsesdfsfdsdfsxv"}

    # Random key set
    correct_dict = {
        "HOST": "hostaddr",
        "USERNAME": "randomstring_unique_string",
        "PATH": "@host.localhost:",
    }

    correct_header = {"Mount": str(correct_dict)}

    # Invalid mount header
    auth_mount_response = session.post(
        "".join([jhub_base_url, "/data"]), headers=wrong_header
    )
    assert auth_mount_response.status_code == 403

    # Valid mount header
    auth_mount_response = session.post(
        "".join([jhub_base_url, "/data"]), headers=correct_header
    )
    assert auth_mount_response.status_code == 200
