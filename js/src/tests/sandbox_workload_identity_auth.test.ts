import { describe, expect, it, jest } from "@jest/globals";
import {
  SandboxClient,
  awsAuth,
  azureAuth,
  azureBlobMount,
  gcpAuth,
  gcsMount,
  mountConfig,
  opaqueSecret,
  proxyConfig,
  s3Mount,
  workspaceSecret,
} from "../sandbox/index.js";
import type { SandboxMountAuth, SandboxMount } from "../sandbox/index.js";

const roleArn = "arn:aws:iam::123456789012:role/SandboxTest";
const tagScope = "tag:7d3c0c1e-1b7a-4e0a-9b8f-2f4a1d2c3b4a";
const wip =
  "//iam.googleapis.com/projects/123456789/locations/global/workloadIdentityPools/langsmith/providers/langsmith";
const saEmail = "vertex-ro@my-project.iam.gserviceaccount.com";
const tenantId = "2c6a46a8-f9b3-4f58-8e5d-4bab8c1f9270";
const clientId = "0b5a3f4e-8f1d-4c3a-9a63-1f6c2d8e7a10";

const s3 = () => [
  s3Mount({ id: "data", mountPath: "/mnt/mounts/data", bucket: "b" }),
];
const gcs = () => [
  gcsMount({
    id: "gcs",
    mountPath: "/mnt/mounts/gcs",
    bucket: "b",
    readOnly: true,
  }),
];
const blob = (storageAccount = "lsdata01", id = "blob") =>
  azureBlobMount({
    id,
    mountPath: `/mnt/mounts/${id}`,
    storageAccount,
    container: "agent-data",
  });

// These calls are checked by tsc, not executed by Jest.
function checkExclusiveOptions() {
  const secret = workspaceSecret("REF");
  awsAuth({
    accessKeyId: secret,
    secretAccessKey: secret,
    // @ts-expect-error subjectScope requires roleArn
    subjectScope: "workspace",
  });
  // @ts-expect-error service account key and workload identity are exclusive
  gcpAuth({ serviceAccountJson: secret, workloadIdentityProvider: wip });
  // @ts-expect-error serviceAccountEmail requires workloadIdentityProvider
  gcpAuth({ serviceAccountJson: secret, serviceAccountEmail: saEmail });
  // @ts-expect-error workload identity and static Azure auth are exclusive
  azureAuth({ tenantId, clientId, storageAccount: "a", accountKey: secret });
  // @ts-expect-error account key and SAS token are exclusive
  azureAuth({ storageAccount: "a", accountKey: secret, sasToken: secret });
  // @ts-expect-error resources requires workload identity
  azureAuth({ storageAccount: "a", sasToken: secret, resources: [] });
}
void checkExclusiveOptions;

describe("sandbox workload identity auth", () => {
  it("adds AWS subjectScope to proxy and mount auth", () => {
    const rule = awsAuth({ roleArn, subjectScope: tagScope });
    expect(rule.aws).toEqual({ role_arn: roleArn, subject_scope: tagScope });
    expect(proxyConfig({ rules: [rule] })).toEqual({ rules: [rule] });
    expect(mountConfig({ auth: [rule], mounts: s3() }).auth).toEqual({
      aws: { role_arn: roleArn, subject_scope: tagScope },
    });
  });

  it("rejects AWS subjectScope without roleArn", () => {
    const secret = workspaceSecret("REF");
    expect(() =>
      awsAuth({
        accessKeyId: secret,
        secretAccessKey: secret,
        subjectScope: "workspace",
      } as never),
    ).toThrow("subjectScope requires roleArn");
    const raw = {
      name: "aws",
      type: "aws",
      aws: {
        access_key_id: secret,
        secret_access_key: secret,
        subject_scope: "workspace",
      },
    } as unknown as SandboxMountAuth;
    expect(() => mountConfig({ auth: [raw], mounts: s3() })).toThrow(
      "subjectScope requires roleArn",
    );
  });

  it("builds a GCP workload identity rule", () => {
    const rule = gcpAuth({
      workloadIdentityProvider: wip,
      serviceAccountEmail: saEmail,
      subjectScope: tagScope,
    });
    expect(rule).toEqual({
      name: "gcp",
      type: "gcp",
      enabled: true,
      gcp: {
        workload_identity_provider: wip,
        service_account_email: saEmail,
        subject_scope: tagScope,
      },
    });
    expect(proxyConfig({ rules: [rule] })).toEqual({ rules: [rule] });
  });

  it.each([
    [
      {
        workloadIdentityProvider: wip,
        serviceAccountJson: workspaceSecret("SA"),
      },
      "mutually exclusive",
    ],
    [
      {
        serviceAccountJson: workspaceSecret("SA"),
        serviceAccountEmail: saEmail,
      },
      "require workloadIdentityProvider",
    ],
    [
      { serviceAccountJson: workspaceSecret("SA"), subjectScope: "workspace" },
      "require workloadIdentityProvider",
    ],
    [{}, "serviceAccountJson or workloadIdentityProvider"],
  ])("gcpAuth rejects mixed or missing credentials %#", (options, message) => {
    expect(() => gcpAuth(options as never)).toThrow(message);
  });

  it("keeps workload identity fields and drops scopes in GCS mount auth", () => {
    const rule = gcpAuth({
      workloadIdentityProvider: wip,
      subjectScope: "workspace",
      scopes: ["https://www.googleapis.com/auth/devstorage.read_only"],
    });
    expect(mountConfig({ auth: [rule], mounts: gcs() }).auth).toEqual({
      gcp: { workload_identity_provider: wip, subject_scope: "workspace" },
    });
  });

  it.each([true, false])(
    "GCS mounts can use an enabled GCP workload identity rule (enabled=%s)",
    (enabled) => {
      const proxy = proxyConfig({
        rules: [gcpAuth({ workloadIdentityProvider: wip, enabled })],
      });
      if (enabled) {
        expect(mountConfig({ proxyConfig: proxy, mounts: gcs() })).toEqual({
          auth: {},
          mounts: gcs(),
        });
      } else {
        expect(() =>
          mountConfig({ proxyConfig: proxy, mounts: gcs() }),
        ).toThrow("gcs mounts require gcp auth");
      }
    },
  );

  it.each([
    [
      {
        tenantId,
        clientId,
        subjectScope: tagScope,
        resources: ["https://storage.azure.com" as const],
      },
      {
        tenant_id: tenantId,
        client_id: clientId,
        subject_scope: tagScope,
        resources: ["https://storage.azure.com"],
      },
    ],
    [
      { storageAccount: "lsdata01", accountKey: opaqueSecret("k") },
      { storage_account: "lsdata01", account_key: opaqueSecret("k") },
    ],
    [
      { storageAccount: "lsdata01", sasToken: workspaceSecret("SAS") },
      { storage_account: "lsdata01", sas_token: workspaceSecret("SAS") },
    ],
  ])("azureAuth builds each form %#", (options, expected) => {
    const rule = azureAuth(options);
    expect(rule).toEqual({
      name: "azure",
      type: "azure",
      enabled: true,
      azure: expected,
    });
    expect(proxyConfig({ rules: [rule] })).toEqual({ rules: [rule] });
  });

  it.each([
    [{ tenantId, clientId, storageAccount: "lsdata01" }, "mutually exclusive"],
    [
      { tenantId, clientId, sasToken: workspaceSecret("SAS") },
      "mutually exclusive",
    ],
    [{ tenantId }, "clientId"],
    [
      {
        storageAccount: "lsdata01",
        accountKey: opaqueSecret("k"),
        sasToken: workspaceSecret("SAS"),
      },
      "exactly one",
    ],
    [{ storageAccount: "lsdata01" }, "exactly one"],
    [{ accountKey: opaqueSecret("k") }, "storageAccount"],
    [
      {
        storageAccount: "lsdata01",
        accountKey: opaqueSecret("k"),
        subjectScope: "workspace",
      },
      "require tenantId and clientId",
    ],
    [
      {
        storageAccount: "lsdata01",
        accountKey: opaqueSecret("k"),
        resources: ["https://storage.azure.com"],
      },
      "require tenantId and clientId",
    ],
  ])("azureAuth rejects mixed or incomplete forms %#", (options, message) => {
    expect(() => azureAuth(options as never)).toThrow(message);
  });

  it("azureBlobMount serializes the backend shape", () => {
    expect(
      azureBlobMount({
        id: "data",
        mountPath: "/mnt/mounts/data",
        storageAccount: "lsdata01",
        container: "agent-data",
        prefix: "runs/",
        readOnly: true,
        cache: { max_size_bytes: 1024 },
      }),
    ).toEqual({
      id: "data",
      type: "azure_blob",
      mount_path: "/mnt/mounts/data",
      azure_blob: {
        storage_account: "lsdata01",
        container: "agent-data",
        prefix: "runs/",
      },
      read_only: true,
      cache: { max_size_bytes: 1024 },
    });
  });

  it.each([
    [
      azureAuth({
        tenantId,
        clientId,
        subjectScope: "workspace",
        resources: ["https://storage.azure.com"],
      }),
      { tenant_id: tenantId, client_id: clientId, subject_scope: "workspace" },
    ],
    [
      azureAuth({ storageAccount: "lsdata01", accountKey: opaqueSecret("k") }),
      { account_key: opaqueSecret("k") },
    ],
    [
      azureAuth({
        storageAccount: "lsdata01",
        sasToken: workspaceSecret("SAS"),
      }),
      { sas_token: workspaceSecret("SAS") },
    ],
  ])("Azure mount auth keeps only mount fields %#", (rule, expected) => {
    expect(mountConfig({ auth: [rule], mounts: [blob()] })).toEqual({
      auth: { azure: expected },
      mounts: [blob()],
    });
  });

  it("Azure Blob mounts can use an enabled Azure proxy rule", () => {
    const proxy = proxyConfig({ rules: [azureAuth({ tenantId, clientId })] });
    expect(mountConfig({ proxyConfig: proxy, mounts: [blob()] })).toEqual({
      auth: {},
      mounts: [blob()],
    });
  });

  it.each<[Parameters<typeof mountConfig>[0], string]>([
    [{ mounts: [blob()] }, "azure_blob mounts require azure auth"],
    [
      {
        mounts: [blob()],
        proxyConfig: proxyConfig({
          rules: [azureAuth({ tenantId, clientId, enabled: false })],
        }),
      },
      "azure_blob mounts require azure auth",
    ],
    [
      {
        mounts: s3(),
        auth: [awsAuth({ roleArn }), azureAuth({ tenantId, clientId })],
      },
      "at least one azure_blob mount",
    ],
    [
      {
        mounts: [blob(), blob("other02", "other")] as SandboxMount[],
        auth: [
          azureAuth({
            storageAccount: "lsdata01",
            sasToken: opaqueSecret("s"),
          }),
        ],
      },
      "storageAccount",
    ],
    [
      {
        mounts: [blob()],
        auth: [azureAuth({ tenantId, clientId })],
        proxyConfig: proxyConfig({
          rules: [azureAuth({ tenantId, clientId })],
        }),
      },
      "both mountConfig and proxyConfig",
    ],
  ])("mountConfig rejects invalid Azure auth %#", (options, message) => {
    expect(() => mountConfig(options)).toThrow(message);
  });

  it("forwards Azure and GCP workload identity config at creation", async () => {
    const proxy = proxyConfig({
      rules: [
        gcpAuth({ workloadIdentityProvider: wip }),
        azureAuth({ tenantId, clientId }),
      ],
    });
    const mounts = mountConfig({
      proxyConfig: proxy,
      mounts: [...gcs(), blob()],
    });
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ name: "wi-box", status: "ready" }), {
        status: 201,
      }),
    );
    const client = new SandboxClient({
      apiEndpoint: "http://test-server:8080",
    });
    jest.spyOn(client, "_fetch").mockImplementation(mockFetch);
    await client.createSandbox("snap-1", {
      proxyConfig: proxy,
      mountConfig: mounts,
    });
    const body = JSON.parse(mockFetch.mock.calls[0][1]?.body as string);
    expect(body.proxy_config).toEqual(proxy);
    expect(body.mount_config).toEqual(mounts);
  });
});
