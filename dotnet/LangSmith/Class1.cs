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
        public required string Name { get; set; }
        public required Dictionary<string, object> Inputs { get; set; }
        public required string RunType { get; set; }
        public required string Id { get; set; }
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
        public string Id { get; set; }
        public bool Success { get; set; }
        public string Message { get; set; }
    }

    public class BatchItem
    {
        public string Type { get; set; } // "create" or "update"
        public object Item { get; set; }
    }

    public class Client
    {
        private readonly HttpClient _httpClient;
        private readonly ClientConfig _config;
        private readonly ConcurrentQueue<BatchItem> _autoBatchQueue = new();

        public Client(ClientConfig config)
        {
            _config = config;
            _httpClient = new HttpClient
            {
                Timeout = TimeSpan.FromMilliseconds(config.TimeoutMs)
            };
            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", config.ApiKey);
        }

        public async Task<RunResult> CreateRunAsync(CreateRunParams runParams)
        {
            if (_config.AutoBatchTracing)
            {
                EnqueueBatchItem(new BatchItem { Type = "create", Item = runParams });
                TriggerBatchProcessingIfNeeded();
                return new RunResult { Success = true, Message = "Run creation queued" };
            }
            else
            {
                await PostAsync("/runs", runParams);
                return new RunResult { Success = true, Message = "Run creation queued" };
            }
        }

        public async Task<RunResult> UpdateRunAsync(string runId, UpdateRunParams runParams)
        {
            if (_config.AutoBatchTracing)
            {
                EnqueueBatchItem(new BatchItem { Type = "update", Item = runParams });
                TriggerBatchProcessingIfNeeded();
                return new RunResult { Success = true, Message = "Run update queued" };
            }
            else
            {
                await PatchAsync($"/runs/{runId}", runParams);
                return new RunResult { Success = true, Message = "Run update queued" };
            }
        }

        private void EnqueueBatchItem(BatchItem item)
        {
            _autoBatchQueue.Enqueue(item);
        }

        private void TriggerBatchProcessingIfNeeded()
        {
            if (_autoBatchQueue.Count >= _config.PendingAutoBatchedRunLimit)
            {
                Task.Run(async () => await ProcessAutoBatchQueueAsync());
            }
        }

        private async Task<RunResult> PostAsync<T>(string path, T data)
        {
            var jsonContent = JsonSerializer.Serialize(data);
            var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");
            var response = await _httpClient.PostAsync($"{_config.ApiUrl}{path}", content);
            response.EnsureSuccessStatusCode();
            var jsonResponse = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<RunResult>(jsonResponse);
        }

        private async Task<RunResult> PatchAsync<T>(string path, T data)
        {
            var jsonContent = JsonSerializer.Serialize(data);
            var content = new StringContent(jsonContent, Encoding.UTF8, "application/json");
            var request = new HttpRequestMessage(HttpMethod.Patch, $"{_config.ApiUrl}{path}") { Content = content };
            var response = await _httpClient.SendAsync(request);
            response.EnsureSuccessStatusCode();
            var jsonResponse = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<RunResult>(jsonResponse);
        }

        private async Task ProcessAutoBatchQueueAsync()
        {
            // Temporary lists to hold batched items
            List<CreateRunParams> createBatchList = new();
            List<UpdateRunParams> updateBatchList = new();

            // Dequeue items while the queue is not empty
            while (_autoBatchQueue.TryDequeue(out var batchItem))
            {
                switch (batchItem.Type)
                {
                    case "create":
                        if (batchItem.Item is CreateRunParams createParams)
                        {
                            createBatchList.Add(createParams);
                        }
                        break;
                    case "update":
                        if (batchItem.Item is UpdateRunParams updateParams)
                        {
                            updateBatchList.Add(updateParams);
                        }
                        break;
                    default:
                        // Handle error or unexpected item type
                        break;
                }

                // Check if we've reached the API's batch size limit or the queue is empty
                if (createBatchList.Count >= _config.PendingAutoBatchedRunLimit || updateBatchList.Count >= _config.PendingAutoBatchedRunLimit)
                {
                    await SendBatchCreate(createBatchList);
                    await SendBatchUpdate(updateBatchList);
                    createBatchList.Clear();
                    updateBatchList.Clear();
                }
            }

            // Process any remaining items in the batch lists
            if (createBatchList.Any() || updateBatchList.Any())
            {
                await SendBatchCreate(createBatchList);
                await SendBatchUpdate(updateBatchList);
            }
        }

        private async Task SendBatchCreate(List<CreateRunParams> createBatchList)
        {
            if (!createBatchList.Any()) return;

            // Assuming the API has an endpoint for batch creating runs
            var path = "/runs/batch/create";
            await PostAsync(path, createBatchList);
        }

        private async Task SendBatchUpdate(List<UpdateRunParams> updateBatchList)
        {
            if (updateBatchList.Count == 0) return;

            // Assuming the API has an endpoint for batch updating runs
            var path = "/runs/batch/update";
            await PostAsync(path, updateBatchList);
        }
    }
}

