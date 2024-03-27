using NUnit.Framework;
using LangSmith;
using System.Threading.Tasks;
using System.Collections.Generic;
using Moq.Protected; // Needed for mocking HttpMessageHandler
using System.Net.Http;
using System.Threading;
using System.Net;
using System.Text.Json;
using Moq;

[TestFixture]
public class ClientTest
{
    private Client _client;
    private ClientConfig _config;
    private Mock<HttpMessageHandler> _handlerMock;

    [SetUp]
    public void Setup()
    {
        _config = new ClientConfig
        {
            ApiUrl = "https://api.smith.langchain.com",
            ApiKey = "test-api-key",
            AutoBatchTracing = true,
            TimeoutMs = 12000,
            PendingAutoBatchedRunLimit = 100
        };

        _handlerMock = new Mock<HttpMessageHandler>();
        var httpClient = new HttpClient(_handlerMock.Object)
        {
            BaseAddress = new System.Uri(_config.ApiUrl),
        };

        _client = new Client(_config, httpClient); // Adjust Client constructor to accept HttpClient for testing
    }

    [Test]
    public async Task CreateRunAsync_WithValidParamsAndAutoBatchTracingEnabled_ReturnsQueuedRunResult()
    {
        // Arrange
        var runParams = new CreateRunParams { Name = "Test Run", Id = "test-id" };
        _config.AutoBatchTracing = true;

        // Simulate queued response without actual HTTP call
        _handlerMock
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>()
            )
            .ReturnsAsync(new HttpResponseMessage
            {
                StatusCode = HttpStatusCode.OK,
                Content = new StringContent(JsonSerializer.Serialize(new RunResult { Success = true, Message = "Run creation queued" }))
            });

        // Act
        var result = await _client.CreateRunAsync(runParams);

        // Assert
        Assert.IsTrue(result.Success);
        Assert.AreEqual("Run creation queued", result.Message);
    }

    [Test]
    public async Task CreateRunAsync_WithValidParamsAndAutoBatchTracingDisabled_ReturnsRunResultFromPostAsync()
    {
        // Arrange
        var runParams = new CreateRunParams();
        _configMock.Setup(c => c.AutoBatchTracing).Returns(false);
        var expectedPath = "/runs";
        var expectedRunResult = new RunResult { Success = true, Message = "Test Run Result" };
        _client.PostAsync<CreateRunParams, RunResult>(expectedPath, runParams).Returns(expectedRunResult);

        // Act
        var result = await _client.CreateRunAsync(runParams);

        // Assert
        Assert.AreEqual(expectedRunResult, result);
        _configMock.Verify(c => c.AutoBatchTracing, Times.Once);
        _client.Verify(c => c.PostAsync<CreateRunParams, RunResult>(expectedPath, runParams), Times.Once);
    }

    [Test]
    public void CreateRunAsync_WithNullParams_ThrowsArgumentNullException()
    {
        // Arrange
        CreateRunParams runParams = null;

        // Act & Assert
        Assert.ThrowsAsync<ArgumentNullException>(() => _client.CreateRunAsync(runParams));
    }
}