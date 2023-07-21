import * as fs from "fs";
import * as path from "path";
import * as util from "util";
import { Command } from "commander";
import * as child_process from "child_process";
import { setEnvironmentVariable } from "../utils/env.js";
import { spawn } from "child_process";

const currentFileName = __filename;
const currentDirName = __dirname;

const program = new Command();

async function getDockerComposeCommand(): Promise<string[]> {
  const exec = util.promisify(child_process.exec);
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

async function pprintServices(servicesStatus: any[]) {
  const services = [];
  for (const service of servicesStatus) {
    const serviceStatus: Record<string, string> = {
      Service: String(service["Service"]),
      Status: String(service["Status"]),
    };
    const publishers = service["Publishers"] || [];
    if (publishers) {
      serviceStatus["PublishedPorts"] = publishers
        .map((publisher: any) => String(publisher["PublishedPort"]))
        .join(", ");
    }
    services.push(serviceStatus);
  }

  const maxServiceLen = Math.max(
    ...services.map((service) => service["Service"].length)
  );
  const maxStateLen = Math.max(
    ...services.map((service) => service["Status"].length)
  );
  const serviceMessage = [
    "\n" +
      "Service".padEnd(maxServiceLen + 2) +
      "Status".padEnd(maxStateLen + 2) +
      "Published Ports",
  ];
  for (const service of services) {
    const serviceStr = service["Service"].padEnd(maxServiceLen + 2);
    const stateStr = service["Status"].padEnd(maxStateLen + 2);
    const portsStr = service["PublishedPorts"] || "";
    serviceMessage.push(serviceStr + stateStr + portsStr);
  }

  let langchainEndpoint = "http://localhost:1984";
  const usedNgrok = services.some((service) =>
    service["Service"].includes("ngrok")
  );
  if (usedNgrok) {
    langchainEndpoint = await getNgrokUrl();
  }

  serviceMessage.push(
    "\nTo connect, set the following environment variables" +
      " in your LangChain application:" +
      "\nLANGCHAIN_TRACING_V2=true" +
      `\nLANGCHAIN_ENDPOINT=${langchainEndpoint}`
  );
  console.info(serviceMessage.join("\n"));
}

async function getNgrokUrl(): Promise<string> {
  const ngrokUrl = "http://localhost:4040/api/tunnels";
  try {
    // const response = await axios.get(ngrokUrl);
    const response = await fetch(ngrokUrl);
    if (response.status !== 200) {
      throw new Error(
        `Could not connect to ngrok console. ${response.status}, ${response.statusText}`
      );
    }
    const result = await response.json();
    const exposedUrl = result["tunnels"][0]["public_url"];
    return exposedUrl;
  } catch (error) {
    throw new Error(`Could not connect to ngrok console. ${error}`);
  }
}

async function createNgrokConfig(authToken: string | null): Promise<string> {
  const configPath = path.join(currentDirName, "ngrok_config.yaml");
  // Check if is a directory
  if (fs.existsSync(configPath) && fs.lstatSync(configPath).isDirectory()) {
    fs.rmdirSync(configPath, { recursive: true });
  } else if (fs.existsSync(configPath)) {
    fs.unlinkSync(configPath);
  }
  let ngrokConfig = `
region: us
tunnels:
  langchain:
    addr: langchain-backend:1984
    proto: http
version: '2'
`;

  if (authToken !== null) {
    ngrokConfig += `authtoken: ${authToken}`;
  }
  fs.writeFileSync(configPath, ngrokConfig);
  return configPath;
}

class SmithCommand {
  dockerComposeCommand: string[] = [];
  dockerComposeFile = "";
  dockerComposeDevFile = "";
  ngrokPath = "";

  constructor({ dockerComposeCommand }: { dockerComposeCommand: string[] }) {
    this.dockerComposeCommand = dockerComposeCommand;
    this.dockerComposeFile = path.join(
      path.dirname(currentFileName),
      "docker-compose.yaml"
    );
    this.dockerComposeDevFile = path.join(
      path.dirname(currentFileName),
      "docker-compose.dev.yaml"
    );
    this.ngrokPath = path.join(
      path.dirname(currentFileName),
      "docker-compose.ngrok.yaml"
    );
  }

  async executeCommand(command: string[]) {
    return new Promise<void>((resolve, reject) => {
      const child = spawn(command[0], command.slice(1), { stdio: "inherit" });

      child.on("error", (error) => {
        console.error(`error: ${error.message}`);
        reject(error);
      });

      child.on("close", (code) => {
        if (code !== 0) {
          reject(new Error(`Process exited with code ${code}`));
        } else {
          resolve();
        }
      });
    });
  }

  public static async create() {
    const dockerComposeCommand = await getDockerComposeCommand();
    return new SmithCommand({ dockerComposeCommand });
  }

  async start(args: any) {
    console.info(
      "BY USING THIS SOFTWARE YOU AGREE TO THE TERMS OF SERVICE AT:"
    );
    console.info("https://smith.langchain.com/terms-of-service.pdf");
    if (args.dev) {
      setEnvironmentVariable("_LANGSMITH_IMAGE_PREFIX", "rc-");
    }
    if (args.openaiApiKey) {
      setEnvironmentVariable("OPENAI_API_KEY", args.openaiApiKey);
    }
    await this.pull(args);
    if (args.expose) {
      await this.startAndExpose(args.ngrokAuthtoken, args.dev);
    } else {
      await this.startLocal(args.dev);
    }
  }

  async pull(args: any) {
    if (args.dev) {
      setEnvironmentVariable("_LANGSMITH_IMAGE_PREFIX", "rc-");
    }

    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "pull",
    ];
    await this.executeCommand(command);
  }

  async startLocal(dev: boolean) {
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
    ];
    if (dev) {
      command.push("-f", this.dockerComposeDevFile);
    }
    command.push("up", "--quiet-pull", "--wait");
    await this.executeCommand(command);
    console.info(
      "LangSmith server is running at http://localhost:1984.\n" +
        "To view the app, navigate your browser to http://localhost:80" +
        "\n\nTo connect your LangChain application to the server" +
        " locally, set the following environment variable" +
        " when running your LangChain application."
    );
    console.info("\tLANGCHAIN_TRACING_V2=true");
  }

  async startAndExpose(ngrokAuthToken: string | null, dev: boolean) {
    const configPath = await createNgrokConfig(ngrokAuthToken);
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "-f",
      this.ngrokPath,
    ];
    if (dev) {
      command.push("-f", this.dockerComposeDevFile);
    }
    command.push("up", "--quiet-pull", "--wait");
    await this.executeCommand(command);
    console.info(
      "ngrok is running. You can view the dashboard at http://0.0.0.0:4040"
    );
    const ngrokUrl = await getNgrokUrl();
    console.info(
      "LangSmith server is running at http://localhost:1984." +
        "To view the app, navigate your browser to http://localhost:80" +
        "\n\nTo connect your LangChain application to the server" +
        " remotely, set the following environment variable" +
        " when running your LangChain application."
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
    await this.executeCommand(command);
  }
  async status() {
    const command = [
      ...this.dockerComposeCommand,
      "-f",
      this.dockerComposeFile,
      "ps",
      "--format",
      "json",
    ];
    const exec = util.promisify(child_process.exec);
    const result = await exec(command.join(" "));
    const servicesStatus = JSON.parse(result.stdout);
    if (servicesStatus) {
      console.info("The LangSmith server is currently running.");
      await pprintServices(servicesStatus);
    } else {
      console.info("The LangSmith server is not running.");
    }
  }
}

const startCommand = new Command("start")
  .description("Start the LangSmith server")
  .option(
    "--expose",
    "Expose the server to the internet via ngrok (requires ngrok to be installed)"
  )
  .option(
    "--ngrok-authtoken <ngrokAuthtoken>",
    "Your ngrok auth token. If this is set, --expose is implied."
  )
  .option("--dev", "Run the development version of the LangSmith server")
  .option(
    "--openai-api-key <openaiApiKey>",
    "Your OpenAI API key. If not provided, the OpenAI API Key will be read" +
      " from the OPENAI_API_KEY environment variable. If neither are provided," +
      " some features of LangSmith will not be available."
  )
  .action(async (args: string[]) => (await SmithCommand.create()).start(args));

const stopCommand = new Command("stop")
  .command("stop")
  .description("Stop the LangSmith server")
  .action(async () => (await SmithCommand.create()).stop());

const pullCommand = new Command("pull")
  .command("pull")
  .description("Pull the latest version of the LangSmith server")
  .option("--dev", "Pull the development version of the LangSmith server")
  .action(async (args: string[]) => (await SmithCommand.create()).pull(args));

const statusCommand = new Command("status")
  .command("status")
  .description("Get the status of the LangSmith server")
  .action(async () => (await SmithCommand.create()).status());

program
  .description("Manage the LangSmith server")
  .addCommand(startCommand)
  .addCommand(stopCommand)
  .addCommand(pullCommand)
  .addCommand(statusCommand);

program.parse(process.argv);
