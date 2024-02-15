using System.Collections.Concurrent;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace LangSmith
{
    public class ClientConfig
    {
        public string ApiUrl { get; set; } = "https://api.smith.langchain.com";
        public string? ApiKey { get; set; }
        public int TimeoutMs { get; set; } = 12000;
        public bool AutoBatchTracing { get; set; } = true;
        public int PendingAutoBatchedRunLimit { get; set; } = 100;
    }

    public class CreateRunParams
    {
        public string? Name { get; set; }
        public Dictionary<string, object>? Inputs { get; set; }
        public string? RunType { get; set; }
        public string? Id { get; set; }
        public long? StartTime { get; set; }
        public long? EndTime { get; set; }
        public Dictionary<string, object>? Extra { get; set; }
        public string? Error { get; set; }
        public object? Serialized { get; set; }
        public Dictionary<string, object>? Outputs { get; set; }
        public string? ReferenceExampleId { get; set; }
        public List<CreateRunParams>? ChildRuns { get; set; }
        public string? ParentRunId { get; set; }
        public string? ProjectName { get; set; }
        public string? RevisionId { get; set; }
        public string? TraceId { get; set; }
        public string? DottedOrder { get; set; }
    }

    public class UpdateRunParams
    {
        public string? Id { get; set; }
        public long? EndTime { get; set; }
        public Dictionary<string, object>? Extra { get; set; }
        public string? Error { get; set; }
        public Dictionary<string, object>? Inputs { get; set; }
        public Dictionary<string, object>? Outputs { get; set; }
        public string? ParentRunId { get; set; }
        public string? ReferenceExampleId { get; set; }
        public List<Dictionary<string, object>>? Events { get; set; }
        public string? SessionId { get; set; }
        public string? TraceId { get; set; }
        public string? DottedOrder { get; set; }
    }

    public class RunResult
    {
        public bool Success { get; set; }
        public string? Message { get; set; }
    }

    public class BatchItem
    {
        public string? Type { get; set; } // "create" or "update"
        public object? Item { get; set; }
    }

    public class Client
    {
        private readonly HttpClient _httpClient;
        private readonly ClientConfig _config;
        private readonly ConcurrentQueue<BatchItem> _autoBatchQueue = new ConcurrentQueue<BatchItem>();
        private IConfig @object;

        public Client(ClientConfig config, HttpClient httpClient)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _httpClient = new HttpClient
            {
                BaseAddress = new Uri(config.ApiUrl),
                Timeout = TimeSpan.FromMilliseconds(config.TimeoutMs)
            };
            if (!string.IsNullOrWhiteSpace(config.ApiKey))
            {
                _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", config.ApiKey);
            }
        }

        public Client(IConfig @object)
        {
            this.@object = @object;
        }

        public async Task<RunResult> CreateRunAsync(CreateRunParams runParams)
        {
            if (runParams != null)
            {
                if (_config.AutoBatchTracing)
                {
                    _autoBatchQueue.Enqueue(new BatchItem { Type = "create", Item = runParams });
                    TriggerBatchProcessingIfNeeded();
                    return new RunResult { Success = true, Message = "Run creation queued" };
                }
                else
                {
                    var path = "/runs";
                    return await PostAsync<CreateRunParams, RunResult>(path, runParams);
                }
            }

            throw new ArgumentNullException(nameof(runParams));
        }

        public async Task<RunResult> UpdateRunAsync(string runId, UpdateRunParams runParams)
        {
            if (string.IsNullOrWhiteSpace(runId))
            {
                throw new ArgumentNullException(nameof(runId));
            }

            if (runParams == null)
            {
                throw new ArgumentNullException(nameof(runParams));
            }

            if (_config.AutoBatchTracing)
            {
                _autoBatchQueue.Enqueue(new BatchItem { Type = "update", Item = runParams });
                TriggerBatchProcessingIfNeeded();
                return new RunResult { Success = true, Message = "Run update queued" };
            }
            else
            {
                var path = $"/runs/{runId}";
                return await PatchAsync<UpdateRunParams, RunResult>(path, runParams);
            }
        }

        private void TriggerBatchProcessingIfNeeded()
        {
            if (_autoBatchQueue.Count >= _config.PendingAutoBatchedRunLimit)
            {
                Task.Run(ProcessAutoBatchQueueAsync);
            }
        }

        private async Task<RunResult> PostAsync<TRequest, TResponse>(string path, TRequest data)
        {
            var jsonContent = JsonSerializer.Serialize(data);
            var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync(path, content);
            response.EnsureSuccessStatusCode();
            var jsonResponse = await response.Content.ReadAsStringAsync();
            var deserializedResponse = JsonSerializer.Deserialize<TResponse>(jsonResponse);
            return deserializedResponse as RunResult ?? default!;
        }

        private async Task<RunResult> PatchAsync<TRequest, TResponse>(string path, TRequest data)
            where TResponse : RunResult
        {
            var jsonContent = JsonSerializer.Serialize(data);
            var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");
            var request = new HttpRequestMessage(HttpMethod.Patch, path) { Content = content };
            var response = await _httpClient.SendAsync(request);
            response.EnsureSuccessStatusCode();
            var jsonResponse = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<TResponse>(jsonResponse) ?? default!;
        }

        private async Task ProcessAutoBatchQueueAsync()
        {
            var batchRequest = new
            {
                post = new List<CreateRunParams>(),
                patch = new List<UpdateRunParams>()
            };

            while (_autoBatchQueue.TryDequeue(out var batchItem))
            {
                switch (batchItem.Type)
                {
                    case "create":
                        if (batchItem.Item is CreateRunParams createParams)
                        {
                            batchRequest.post.Add(createParams);
                        }
                        break;
                    case "update":
                        if (batchItem.Item is UpdateRunParams updateParams)
                        {
                            batchRequest.patch.Add(updateParams);
                        }
                        break;
                }

                if (batchRequest.post.Count + batchRequest.patch.Count >= _config.PendingAutoBatchedRunLimit)
                {
                    await SendBatchRequest(batchRequest);
                    batchRequest.post.Clear();
                    batchRequest.patch.Clear();
                }
            }

            if (batchRequest.post.Count != 0 || batchRequest.patch.Count != 0)
            {
                await SendBatchRequest(batchRequest);
            }
        }

        private async Task SendBatchRequest(dynamic batchRequest)
        {
            if (!batchRequest.post.Any() && !batchRequest.patch.Any())
            {
                return;
            }

            var path = "/runs/batch";
            await PostAsync<dynamic, RunResult>(path, batchRequest);
        }
    }
}
