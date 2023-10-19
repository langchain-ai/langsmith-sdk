import argparse
import json
import logging
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Literal, Mapping, Optional, Union, cast

import requests

from langsmith import env as ls_env
from langsmith import utils as ls_utils

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_DIR = Path(__file__).parent


def pprint_services(services_status: List[Mapping[str, Union[str, List[str]]]]) -> None:
    # Loop through and collect Service, State, and Publishers["PublishedPorts"]
    # for each service
    services = []
    for service in services_status:
        service_status: Dict[str, str] = {
            "Service": str(service["Service"]),
            "Status": str(service["Status"]),
        }
        publishers = cast(List[Dict], service.get("Publishers", []))
        if publishers:
            service_status["PublishedPorts"] = ", ".join(
                [str(publisher["PublishedPort"]) for publisher in publishers]
            )
        services.append(service_status)

    max_service_len = max(len(service["Service"]) for service in services)
    max_state_len = max(len(service["Status"]) for service in services)
    service_message = [
        "\n"
        + "Service".ljust(max_service_len + 2)
        + "Status".ljust(max_state_len + 2)
        + "Published Ports"
    ]
    for service in services:
        service_str = service["Service"].ljust(max_service_len + 2)
        state_str = service["Status"].ljust(max_state_len + 2)
        ports_str = service.get("PublishedPorts", "")
        service_message.append(service_str + state_str + ports_str)

    langchain_endpoint: str = "http://localhost:1984"
    used_ngrok = any(["ngrok" in service["Service"] for service in services])
    if used_ngrok:
        langchain_endpoint = get_ngrok_url(auth_token=None)

    service_message.append(
        "\nTo connect, set the following environment variables"
        " in your LangChain application:"
        "\nLANGCHAIN_TRACING_V2=true"
        f"\nLANGCHAIN_ENDPOINT={langchain_endpoint}"
    )
    logger.info("\n".join(service_message))


def get_ngrok_url(auth_token: Optional[str]) -> str:
    """Get the ngrok URL for the LangSmith server."""
    ngrok_url = "http://localhost:4040/api/tunnels"
    try:
        response = requests.get(ngrok_url)
        response.raise_for_status()
        exposed_url = response.json()["tunnels"][0]["public_url"]
    except requests.exceptions.HTTPError:
        raise ValueError("Could not connect to ngrok console.")
    except (KeyError, IndexError):
        message = "ngrok failed to start correctly. "
        if auth_token is not None:
            message += "Please check that your authtoken is correct."
        raise ValueError(message)
    return exposed_url


def _dumps_yaml(config: dict, depth: int = 0) -> str:
    """Dump a dictionary to a YAML string without using any imports.

    We can assume it's all strings, ints, or dictionaries, up to 3 layers deep
    """
    lines = []
    prefix = "  " * depth
    for key, value in config.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_dumps_yaml(value, depth + 1))
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)


@contextmanager
def create_ngrok_config(
    auth_token: Optional[str] = None,
) -> Generator[Path, None, None]:
    """Create the ngrok configuration file."""
    config_path = _DIR / "ngrok_config.yaml"
    if config_path.exists():
        # If there was an error in a prior run, it's possible
        # Docker made this a directory instead of a file
        if config_path.is_dir():
            shutil.rmtree(config_path)
        else:
            config_path.unlink()
    ngrok_config = {
        "tunnels": {
            "langchain": {
                "proto": "http",
                "addr": "langchain-backend:1984",
            }
        },
        "version": "2",
        "region": "us",
    }
    if auth_token is not None:
        ngrok_config["authtoken"] = auth_token
    config_path = _DIR / "ngrok_config.yaml"
    with config_path.open("w") as f:
        s = _dumps_yaml(ngrok_config)
        f.write(s)
    yield config_path
    # Delete the config file after use
    config_path.unlink(missing_ok=True)


class LangSmithCommand:
    """Manage the LangSmith Tracing server."""

    def __init__(self) -> None:
        self.docker_compose_file = (
            Path(__file__).absolute().parent / "docker-compose.yaml"
        )
        self.docker_compose_dev_file = (
            Path(__file__).absolute().parent / "docker-compose.dev.yaml"
        )
        self.docker_compose_beta_file = (
            Path(__file__).absolute().parent / "docker-compose.beta.yaml"
        )
        self.ngrok_path = Path(__file__).absolute().parent / "docker-compose.ngrok.yaml"

    @property
    def docker_compose_command(self) -> List[str]:
        return ls_utils.get_docker_compose_command()

    def _open_browser(self, url: str) -> None:
        try:
            subprocess.run(["open", url])
        except FileNotFoundError:
            pass

    def _start_local(
        self, stage: Union[Literal["prod"], Literal["dev"], Literal["beta"]] = "prod"
    ) -> None:
        command = [
            *self.docker_compose_command,
            "-f",
            str(self.docker_compose_file),
        ]
        if stage == "dev":
            command.append("-f")
            command.append(str(self.docker_compose_dev_file))
        elif stage == "beta":
            command.append("-f")
            command.append(str(self.docker_compose_beta_file))
        subprocess.run(
            [
                *command,
                "up",
                "--quiet-pull",
                "--wait",
            ]
        )
        logger.info(
            "LangSmith server is running at http://localhost:1984.\n"
            "To view the app, navigate your browser to http://localhost:80"
            "\n\nTo connect your LangChain application to the server"
            " locally,\nset the following environment variable"
            " when running your LangChain application.\n"
        )

        logger.info("\tLANGCHAIN_TRACING_V2=true")
        self._open_browser("http://localhost")

    def _start_and_expose(
        self,
        auth_token: Optional[str],
        stage: Union[Literal["prod"], Literal["dev"], Literal["beta"]],
    ) -> None:
        with create_ngrok_config(auth_token=auth_token):
            command = [
                *self.docker_compose_command,
                "-f",
                str(self.docker_compose_file),
                "-f",
                str(self.ngrok_path),
            ]
            if stage == "dev":
                command.append("-f")
                command.append(str(self.docker_compose_dev_file))
            elif stage == "beta":
                command.append("-f")
                command.append(str(self.docker_compose_beta_file))

            subprocess.run(
                [
                    *command,
                    "up",
                    "--quiet-pull",
                    "--wait",
                ]
            )
        logger.info(
            "ngrok is running. You can view the dashboard at http://0.0.0.0:4040"
        )
        ngrok_url = get_ngrok_url(auth_token)
        logger.info(
            "LangSmith server is running at http://localhost:1984."
            "\nTo view the app, navigate your browser to http://localhost:80"
            " To connect remotely, set the following environment"
            " variable when running your LangChain application."
        )
        logger.info("\tLANGCHAIN_TRACING_V2=true")
        logger.info(f"\tLANGCHAIN_ENDPOINT={ngrok_url}")
        self._open_browser("http://0.0.0.0:4040")
        self._open_browser("http://localhost")

    def pull(
        self,
        *,
        stage: Union[Literal["prod"], Literal["dev"], Literal["beta"]] = "prod",
    ) -> None:
        """Pull the latest LangSmith images.

        Args:
            stage: Which stage of LangSmith images to pull.
                One of "prod", "dev", or "beta".
        """
        if stage == "dev":
            os.environ["_LANGSMITH_IMAGE_PREFIX"] = "dev-"
        elif stage == "beta":
            os.environ["_LANGSMITH_IMAGE_PREFIX"] = "rc-"
        subprocess.run(
            [
                *self.docker_compose_command,
                "-f",
                str(self.docker_compose_file),
                "pull",
            ]
        )

    def start(
        self,
        *,
        expose: bool = False,
        auth_token: Optional[str] = None,
        stage: Union[Literal["prod"], Literal["dev"], Literal["beta"]] = "prod",
        openai_api_key: Optional[str] = None,
    ) -> None:
        """Run the LangSmith server locally.

        Args:
            expose: If True, expose the server to the internet using ngrok.
            auth_token: The ngrok authtoken to use (visible in the ngrok dashboard).
                If not provided, ngrok server session length will be restricted.
            stage: Which set of images to pull when running.
                One of "prod", "dev", or "beta".
            openai_api_key: The OpenAI API key to use for LangSmith
                If not provided, the OpenAI API Key will be read from the
                OPENAI_API_KEY environment variable. If neither are provided,
                some features of LangSmith will not be available.
        """
        if stage == "dev":
            os.environ["_LANGSMITH_IMAGE_PREFIX"] = "dev-"
        elif stage == "beta":
            os.environ["_LANGSMITH_IMAGE_PREFIX"] = "rc-"
        if openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        self.pull(stage=stage)
        if expose:
            self._start_and_expose(auth_token=auth_token, stage=stage)
        else:
            self._start_local(stage=stage)

    def stop(self, clear_volumes: bool = False) -> None:
        """Stop the LangSmith server."""
        cmd = [
            *self.docker_compose_command,
            "-f",
            str(self.docker_compose_file),
            "-f",
            str(self.ngrok_path),
            "down",
        ]
        if clear_volumes:
            confirm = input(
                "You are about to delete all the locally cached "
                "LangSmith containers and volumes. "
                "This operation cannot be undone. Are you sure? [y/N]"
            )
            if confirm.lower() != "y":
                print("Aborting.")
                return
            cmd.append("--volumes")

        subprocess.run(cmd)

    def logs(self) -> None:
        """Print the logs from the LangSmith server."""
        subprocess.run(
            [
                *self.docker_compose_command,
                "-f",
                str(self.docker_compose_file),
                "-f",
                str(self.ngrok_path),
                "logs",
            ]
        )

    def status(self) -> None:
        """Provide information about the status LangSmith server."""

        command = [
            *self.docker_compose_command,
            "-f",
            str(self.docker_compose_file),
            "ps",
            "--format",
            "json",
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            command_stdout = result.stdout.decode("utf-8")
            services_status = json.loads(command_stdout)
        except json.JSONDecodeError:
            logger.error("Error checking LangSmith server status.")
            return
        if services_status:
            logger.info("The LangSmith server is currently running.")
            pprint_services(services_status)
        else:
            logger.info("The LangSmith server is not running.")
            return


def env() -> None:
    """Print the runtime environment information."""
    env = ls_env.get_runtime_environment()
    env.update(ls_env.get_docker_environment())
    env.update(ls_env.get_langchain_env_vars())

    # calculate the max length of keys
    max_key_length = max(len(key) for key in env.keys())

    logger.info("LangChain Environment:")
    for k, v in env.items():
        logger.info(f"{k:{max_key_length}}: {v}")


def main() -> None:
    """Main entrypoint for the CLI."""
    print("BY USING THIS SOFTWARE YOU AGREE TO THE TERMS OF SERVICE AT:")
    print("https://smith.langchain.com/terms-of-service.pdf")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(description="LangSmith CLI commands")

    server_command = LangSmithCommand()
    server_start_parser = subparsers.add_parser(
        "start", description="Start the LangSmith server."
    )
    server_start_parser.add_argument(
        "--expose",
        action="store_true",
        help="Expose the server to the internet using ngrok.",
    )
    server_start_parser.add_argument(
        "--ngrok-authtoken",
        default=os.getenv("NGROK_AUTHTOKEN"),
        help="The ngrok authtoken to use (visible in the ngrok dashboard)."
        " If not provided, ngrok server session length will be restricted.",
    )
    server_start_parser.add_argument(
        "--stage",
        default="prod",
        choices=["prod", "dev", "beta"],
        help="Which set of images to pull when running.",
    )
    server_start_parser.add_argument(
        "--openai-api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="The OpenAI API key to use for LangSmith."
        " If not provided, the OpenAI API Key will be read from the"
        " OPENAI_API_KEY environment variable. If neither are provided,"
        " some features of LangSmith will not be available.",
    )
    server_start_parser.add_argument(
        "--langsmith-license-key",
        default=os.getenv("LANGSMITH_LICENSE_KEY"),
        help="The LangSmith license key to use for LangSmith."
        " If not provided, the LangSmith License Key will be read from the"
        " LANGSMITH_LICENSE_KEY environment variable. If neither are provided,"
        " the Langsmith application will not spin up.",
    )
    server_start_parser.set_defaults(
        func=lambda args: server_command.start(
            expose=args.expose,
            auth_token=args.ngrok_authtoken,
            stage=args.stage,
            openai_api_key=args.openai_api_key,
        )
    )

    server_stop_parser = subparsers.add_parser(
        "stop", description="Stop the LangSmith server."
    )
    server_stop_parser.add_argument(
        "--clear-volumes",
        action="store_true",
        help="Delete all the locally cached LangSmith containers and volumes.",
    )
    server_stop_parser.set_defaults(
        func=lambda args: server_command.stop(clear_volumes=args.clear_volumes)
    )

    server_pull_parser = subparsers.add_parser(
        "pull", description="Pull the latest LangSmith images."
    )
    server_pull_parser.add_argument(
        "--stage",
        default="prod",
        choices=["prod", "dev", "beta"],
        help="Which stage of LangSmith images to pull.",
    )
    server_pull_parser.set_defaults(
        func=lambda args: server_command.pull(stage=args.stage)
    )
    server_logs_parser = subparsers.add_parser(
        "logs", description="Show the LangSmith server logs."
    )
    server_logs_parser.set_defaults(func=lambda args: server_command.logs())
    server_status_parser = subparsers.add_parser(
        "status", description="Show the LangSmith server status."
    )
    server_status_parser.set_defaults(func=lambda args: server_command.status())
    env_parser = subparsers.add_parser("env")
    env_parser.set_defaults(func=lambda args: env())

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
