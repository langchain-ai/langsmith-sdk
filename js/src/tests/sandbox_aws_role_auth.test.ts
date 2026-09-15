import { describe, expect, it, jest } from "@jest/globals";
import {
  SandboxClient,
  awsAuth,
  mountConfig,
  opaqueSecret,
  proxyConfig,
  s3Mount,
  workspaceSecret,
} from "../sandbox/index.js";
import type {
  CreateSandboxOptions,
  SandboxAwsAuthRule,
} from "../sandbox/types.js";

const roleArn = "arn:aws:iam::123456789012:role/SandboxTest";
const mounts = () => [
  s3Mount({ id: "data", mountPath: "/mnt/data", bucket: "test-bucket" }),
];

// These calls are checked by tsc, not executed by Jest.
function checkAuthAlternatives() {
  const key = workspaceSecret("AWS_KEY_ID_REF");
  const secret = workspaceSecret("AWS_KEY_VALUE_REF");
  const staticRule = awsAuth({ accessKeyId: key, secretAccessKey: secret });
  const roleRule = awsAuth({ roleArn });
  const keyValue: string = staticRule.aws.access_key_id.value;
  const roleValue: string = roleRule.aws.role_arn;
  // @ts-expect-error role and static alternatives are exclusive
  awsAuth({ roleArn, accessKeyId: key, secretAccessKey: secret });
  // @ts-expect-error static auth requires both keys
  awsAuth({ accessKeyId: key });
  // @ts-expect-error an authentication alternative is required
  awsAuth({});
  const mixed: SandboxAwsAuthRule = {
    name: "bad",
    type: "aws",
    // @ts-expect-error raw AWS rules also require exclusive alternatives
    aws: { role_arn: roleArn, access_key_id: key, secret_access_key: secret },
  };
  void [keyValue, roleValue, mixed];
}
void checkAuthAlternatives;

describe("sandbox AWS role auth", () => {
  it("builds a role-only descriptor", () => {
    expect(
      awsAuth({ roleArn, name: "role", envVars: { AWS_REGION: "us-east-1" } }),
    ).toEqual({
      name: "role",
      type: "aws",
      enabled: true,
      env_vars: { AWS_REGION: "us-east-1" },
      aws: { role_arn: roleArn },
    });
  });

  it.each([workspaceSecret, opaqueSecret])(
    "preserves static credential payloads",
    (secret) => {
      const options = {
        accessKeyId: secret("AWS_KEY_ID_REF"),
        secretAccessKey: secret("AWS_KEY_VALUE_REF"),
      };
      const rule = awsAuth(options);
      expect(rule.aws).toEqual({
        access_key_id: options.accessKeyId,
        secret_access_key: options.secretAccessKey,
      });
      expect(awsAuth({ ...options, roleArn: "" }).aws).toEqual(rule.aws);
      expect(mountConfig({ auth: [rule], mounts: mounts() }).auth.aws).toEqual(
        rule.aws,
      );
    },
  );

  it.each([
    {},
    { roleArn: "" },
    { roleArn: " " },
    { roleArn: 42 },
    { accessKeyId: workspaceSecret("AWS_KEY_ID_REF") },
    { roleArn, accessKeyId: workspaceSecret("AWS_KEY_ID_REF") },
    { roleArn, secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF") },
  ])("rejects incomplete and mixed helper options", (options) => {
    expect(() => awsAuth(options as never)).toThrow();
  });

  it.each([
    { access_key_id: null },
    { secret_access_key: null },
    { external_id: "caller-controlled" },
    { session_token: "not-accepted" },
  ])("rejects extra fields in raw role descriptors", (extra) => {
    const rule = {
      name: "role",
      type: "aws",
      enabled: true,
      aws: { role_arn: roleArn, ...extra },
    };
    expect(() => proxyConfig({ rules: [rule] })).toThrow("only role_arn");
    expect(() =>
      mountConfig({ auth: [rule as never], mounts: mounts() }),
    ).toThrow("only role_arn");
  });

  it("preserves mount-scoped roles under auth.aws", () => {
    expect(
      mountConfig({ auth: [awsAuth({ roleArn })], mounts: mounts() }).auth,
    ).toEqual({ aws: { role_arn: roleArn } });
  });

  it("does not turn general proxy auth into mount-scoped auth", () => {
    const proxy = proxyConfig({ rules: [awsAuth({ roleArn })] });
    expect(mountConfig({ proxyConfig: proxy, mounts: mounts() })).toEqual({
      auth: {},
      mounts: mounts(),
    });
    expect(() =>
      mountConfig({
        proxyConfig: proxy,
        auth: [awsAuth({ roleArn })],
        mounts: mounts(),
      }),
    ).toThrow("both mountConfig and proxyConfig");
  });

  it.each([
    undefined,
    { rules: [] },
    proxyConfig({ rules: [awsAuth({ roleArn, enabled: false })] }),
  ])("requires enabled auth for mounts", (proxy) => {
    expect(() => mountConfig({ proxyConfig: proxy, mounts: mounts() })).toThrow(
      "s3 mounts require aws auth",
    );
  });

  it.each(["proxy", "mount", "shared"])(
    "sends the correct %s auth shape at creation",
    async (mode) => {
      const options: CreateSandboxOptions = {};
      if (mode !== "mount")
        options.proxyConfig = proxyConfig({ rules: [awsAuth({ roleArn })] });
      if (mode === "mount")
        options.mountConfig = mountConfig({
          auth: [awsAuth({ roleArn })],
          mounts: mounts(),
        });
      if (mode === "shared")
        options.mountConfig = mountConfig({
          proxyConfig: options.proxyConfig,
          mounts: mounts(),
        });
      const mockFetch = jest.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ name: "role-box", status: "ready" }), {
          status: 201,
        }),
      );
      const client = new SandboxClient({
        apiEndpoint: "http://test-server:8080",
      });
      jest.spyOn(client, "_fetch").mockImplementation(mockFetch);
      expect((await client.createSandbox("snap-1", options)).name).toBe(
        "role-box",
      );
      const body = JSON.parse(mockFetch.mock.calls[0][1]?.body as string);
      expect(body.proxy_config).toEqual(options.proxyConfig);
      expect(body.mount_config).toEqual(options.mountConfig);
    },
  );

  it("reads mixed static and role sandboxes through list/get", async () => {
    const staticAuth = {
      access_key_id: { type: "opaque" },
      secret_access_key: { type: "opaque" },
    };
    const boxes = [
      {
        name: "static-box",
        mount_config: { auth: { aws: staticAuth }, mounts: mounts() },
      },
      {
        name: "role-box",
        mount_config: {
          auth: { aws: { role_arn: roleArn } },
          mounts: mounts(),
        },
      },
      {
        name: "proxy-box",
        proxy_config: proxyConfig({ rules: [awsAuth({ roleArn })] }),
      },
    ];
    const mockFetch = jest
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ sandboxes: boxes })),
      );
    for (const box of boxes)
      mockFetch.mockResolvedValueOnce(new Response(JSON.stringify(box)));
    const client = new SandboxClient({
      apiEndpoint: "http://test-server:8080",
    });
    jest.spyOn(client, "_fetch").mockImplementation(mockFetch);
    expect((await client.listSandboxes()).map((box) => box.name)).toEqual(
      boxes.map((box) => box.name),
    );
    for (const box of boxes)
      expect((await client.getSandbox(box.name)).name).toBe(box.name);
  });
});
