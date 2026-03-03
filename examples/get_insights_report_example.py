import json
import os

from langsmith import Client


def main() -> None:
    api_url = "https://dev.api.smith.langchain.com"
    api_key = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        raise SystemExit("Set LANGCHAIN_API_KEY (or LANGSMITH_API_KEY) in your environment")
    client = Client(api_url=api_url, api_key=api_key)

    # From URL like: dev.smith.langchain.com/.../projects/p/{project_id}?clusterJobId={report_id}
    # project_id = session/tracing project (path: .../projects/p/71a13ede-...)
    # report_id = insights clustering job id (query: clusterJobId=8fbd954b-...), NOT insightsConfigId
    project_id = "71a13ede-fe30-46a8-aa8d-41c3cdd3d29d"
    report_id = "8fbd954b-29a5-4484-bd69-87e80117b3e8"

    report = client.get_insights_report(id=report_id, project_id=project_id)

    # Save full report as raw JSON
    out_path = "insights_report.json"
    with open(out_path, "w") as f:
        json.dump(report.to_json(), f, indent=2)
    print(f"Saved report to {out_path}")

    # List clusters and get one by name
    if report.clusters:
        first_cluster_name = report.clusters[0].name
        print(f"Clusters: {[c.name for c in report.clusters]}")
        cluster = report.clusters[first_cluster_name]
        desc = (cluster.description or "")[:60]
        if len(cluster.description or "") > 60:
            desc += "..."
        print(f"Cluster {cluster.name!r}: {cluster.num_runs} runs — {desc}")
        traces = cluster.load_traces()
        print(f"Loaded {len(traces)} traces for {cluster.name!r}")


if __name__ == "__main__":
    main()

