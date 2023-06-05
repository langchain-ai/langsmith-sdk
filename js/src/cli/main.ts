import * as fs from "fs";
import * as path from "path";
import * as util from "util";
import { Command } from "commander";
import * as child_process from "child_process";
import * as yaml from "js-yaml";
import { setEnvironmentVariable } from "../utils/env.js";

const exec = util.promisify(child_process.exec);

const program = new Command();

async function getDockerComposeCommand(): Promise<string[]> {
  try {
    await exec("docker compose --version");
    return ["docker", "compose"];
  } catch {
    try {
      await exec("docker-compose --version");
      return ["docker-compose"];
    } catch {
      throw new Error(
        "Neither 'docker compose' nor 'docker-compose' commands are available. Please install the Docker server following the instructions for your operating system at https://docs.docker.com/engine/install/"
      );
    }
  }
}

async function getNgrokUrl(): Promise<string> {
  const ngrokUrl = "http://localhost:4040/api/tunnels";
  try {
    // const response = await axios.get(ngrokUrl);
    const response = await fetch(ngrokUrl);
    if (response.status !== 200) {
      throw new Error("Could not connect to ngrok console.");
    }
    const result = await response.json();
    const exposedUrl = result.data["tunnels"][0]["public_url"];
    return exposedUrl;
  } catch (error) {
    throw new Error("Could not connect to ngrok console.");
  }
}

async function createNgrokConfig(authToken: string | null): Promise<string> {
  const configPath = path.join(__dirname, "ngrok_config.yaml");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ngrokConfig: Record<string, any> = {
    tunnels: {
      langchain: {
        proto: "http",
        addr: "langchain-backend:8000",
      },
    },
    version: "2",
    region: "us",
  };

  if (authToken !== null) {
    ngrokConfig["authtoken"] = authToken;
  }

  fs.writeFileSync(configPath, yaml.dump(ngrokConfig));
  return configPath;
}

class PlusCommand {
  dockerComposeCommand: string[] = [];
  dockerComposeFile = "";
  ngrokPath = "";

  constructor({ dockerComposeCommand }: { dockerComposeCommand: string[] }) {
    this.dockerComposeCommand = dockerComposeCommand;
    this.dockerComposeFile = path.join(
      path.dirname(__filename),
      "docker-compose.yaml"
    );
    this.ngrokPath = path.join(
      path.dirname(__filename),
      "docker-compose.ngrok.yaml"
    );
  }

  public static async create() {
    const dockerComposeCommand = await getDockerComposeCommand();
    return new PlusCommand({ dockerComposeCommand });
  }

  async start(args: any) {
    if (args.dev) {
      setEnvironmentVariable("_LANGCHAINPLUS_IMAGE_PREFIX", "rc-");
    }
    if (args.openaiApiKey) {
      setEnvironmentVariable("OPENAI_API_KEY", args.openaiApiKey);
    }

    if (args.expose) {
      await this.startAndExpose(args.ngrokAuthtoken);
    } else {
      await this.startLocal();
    }
  }

  async startLocal() {
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "up",
      "--pull=always",
      "--quiet-pull",
      "--wait",
    ];
    await exec(command.join(" "));
    console.info(
      "langchain plus server is running at http://localhost.  To connect locally, set the following environment variable when running your LangChain application."
    );
    console.info("\tLANGCHAIN_TRACING_V2=true");
  }

  async startAndExpose(ngrokAuthToken: string | null) {
    const configPath = await createNgrokConfig(ngrokAuthToken);
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "-f",
      configPath,
      "up",
      "--pull=always",
      "--quiet-pull",
      "--wait",
    ];
    await exec(command.join(" "));
    console.info(
      "ngrok is running. You can view the dashboard at http://0.0.0.0:4040"
    );
    const ngrokUrl = await getNgrokUrl();
    console.info(
      "langchain plus server is running at http://localhost. To connect remotely, set the following environment variable when running your LangChain application."
    );
    console.info("\tLANGCHAIN_TRACING_V2=true");
    console.info(`\tLANGCHAIN_ENDPOINT=${ngrokUrl}`);

    fs.unlinkSync(configPath);
  }

  async stop() {
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "-f",
      this.ngrokPath,
      "down",
    ];
    await exec(command.join(" "));
  }
}

program
  .command("start")
  .description("Start the langchain plus server")
  .option(
    "--expose",
    "Expose the server to the internet via ngrok (requires ngrok to be installed)"
  )
  .option(
    "--ngrok-authtoken <ngrokAuthtoken>",
    "Your ngrok auth token. If this is set, --expose is implied."
  )
  .option("--dev", "Run the development version of the langchain plus server")
  .option(
    "--openai-api-key <openaiApiKey>",
    "Your OpenAI API key. If this is set, the server will be able to process text and return enhanced plus results."
  )
  .action(async (args: string[]) => (await PlusCommand.create()).start(args));

program
  .command("stop")
  .description("Stop the langchain plus server")
  .action(async () => (await PlusCommand.create()).stop());

program.parse(process.argv);
